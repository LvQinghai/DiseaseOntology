"""
Layer 3: Cypher 生成中间层

功能:
- 将解析后的实体/关系数据转换为标准 Cypher 语句
- 自动处理前缀添加（label 前缀 / 关系类型前缀）
- 支持 CREATE（新建）和 MERGE（追加）两种策略
- 自动提取额外属性列
"""

from dataclasses import dataclass, field

from backend.services.excel_detector import ParsedSheet


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class CypherStatement:
    """单条 Cypher 语句"""
    statement: str
    params: dict
    description: str               # "CREATE (:MED_Disease {name: '高血压'})"


@dataclass
class CypherBatch:
    """一批 Cypher 语句"""
    entity_statements: list[CypherStatement] = field(default_factory=list)
    relationship_statements: list[CypherStatement] = field(default_factory=list)
    entity_count: int = 0
    relationship_count: int = 0

    def all_statements(self) -> list[CypherStatement]:
        return self.entity_statements + self.relationship_statements

    @property
    def total_operations(self) -> int:
        return self.entity_count + self.relationship_count


# ---------------------------------------------------------------------------
# 生成器
# ---------------------------------------------------------------------------

class CypherGenerator:
    """Cypher 语句生成器"""

    # UNWIND 批量上限（避免单条语句过大）
    UNWIND_BATCH_SIZE = 500

    def __init__(self, prefix: str):
        self.prefix = prefix

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def generate(
        self,
        entity_sheet: ParsedSheet | None,
        relationship_sheet: ParsedSheet | None,
        strategy: str = "CREATE",      # "CREATE" | "MERGE"
    ) -> CypherBatch:
        """
        从 ParsedSheet 生成完整 CypherBatch。

        Args:
            entity_sheet: 实体 Sheet（可选）
            relationship_sheet: 关系 Sheet（可选）
            strategy: CREATE（新建，快）或 MERGE（追加，防重复）
        """
        batch = CypherBatch()

        if entity_sheet:
            gen_fn = self._generate_entity_create if strategy == "CREATE" else self._generate_entity_merge
            batch.entity_statements = gen_fn(entity_sheet)
            # 基于实际生成的语句数计算（过滤空 label 后的有效行）
            batch.entity_count = self._count_rows_in_statements(batch.entity_statements)

        if relationship_sheet:
            batch.relationship_statements = self._generate_relationship(relationship_sheet)
            batch.relationship_count = self._count_rows_in_statements(batch.relationship_statements)

        return batch

    def generate_entity_statements(
        self, entity_sheet: ParsedSheet, strategy: str = "CREATE"
    ) -> list[CypherStatement]:
        """仅生成实体 Cypher 语句（用于增量生成）。"""
        if strategy == "CREATE":
            return self._generate_entity_create(entity_sheet)
        return self._generate_entity_merge(entity_sheet)

    def generate_relationship_statements(
        self, relationship_sheet: ParsedSheet
    ) -> list[CypherStatement]:
        """仅生成关系 Cypher 语句。"""
        return self._generate_relationship(relationship_sheet)

    # ------------------------------------------------------------------
    # 实体生成
    # ------------------------------------------------------------------

    def _generate_entity_create(self, sheet: ParsedSheet) -> list[CypherStatement]:
        """CREATE 模式：每个 label 一组 UNWIND 批量创建。"""
        statements: list[CypherStatement] = []
        # 按 label 分组
        groups: dict[str, list[dict]] = {}
        for row in sheet.rows:
            label = str(row.get("label", "")).strip()
            if not label:
                continue
            full_label = self._full_label(label)
            groups.setdefault(full_label, []).append(self._extract_entity_props(row))

        for full_label, rows in groups.items():
            for i in range(0, len(rows), self.UNWIND_BATCH_SIZE):
                batch = rows[i:i + self.UNWIND_BATCH_SIZE]
                stmt = CypherStatement(
                    statement=(
                        f"UNWIND $batch AS row "
                        f"CREATE (n:`{full_label}`) "
                        f"SET n = row.props "
                        f"RETURN count(n) AS created"
                    ),
                    params={"batch": [{"props": r} for r in batch]},
                    description=(
                        f"CREATE {len(batch)} 个 `{full_label}` 节点"
                    ),
                )
                statements.append(stmt)

        return statements

    def _generate_entity_merge(self, sheet: ParsedSheet) -> list[CypherStatement]:
        """MERGE 模式：按 name 匹配，存在则更新属性，不存在则创建。"""
        statements: list[CypherStatement] = []
        groups: dict[str, list[dict]] = {}
        for row in sheet.rows:
            label = str(row.get("label", "")).strip()
            if not label:
                continue
            full_label = self._full_label(label)
            groups.setdefault(full_label, []).append(self._extract_entity_props(row))

        for full_label, rows in groups.items():
            for i in range(0, len(rows), self.UNWIND_BATCH_SIZE):
                batch = rows[i:i + self.UNWIND_BATCH_SIZE]
                stmt = CypherStatement(
                    statement=(
                        f"UNWIND $batch AS row "
                        f"MERGE (n:`{full_label}` {{name: row.name}}) "
                        f"ON CREATE SET n = row.props "
                        f"ON MATCH SET n += row.props "
                        f"RETURN count(n) AS created"
                    ),
                    params={"batch": [{"name": r["name"], "props": r} for r in batch]},
                    description=(
                        f"MERGE {len(batch)} 个 `{full_label}` 节点"
                    ),
                )
                statements.append(stmt)

        return statements

    # ------------------------------------------------------------------
    # 关系生成
    # ------------------------------------------------------------------

    def _generate_relationship(self, sheet: ParsedSheet) -> list[CypherStatement]:
        """关系批量创建（使用 APOC 动态类型）。"""
        statements: list[CypherStatement] = []

        # 收集有效行
        rows_data: list[dict] = []
        for row in sheet.rows:
            src = str(row.get("source_name", "")).strip()
            rtype = str(row.get("type", "")).strip()
            tgt = str(row.get("target_name", "")).strip()
            if not src or not rtype or not tgt:
                continue
            full_type = self._full_rel_type(rtype)
            props = {}
            for k, v in row.items():
                if k not in ("_row", "source_name", "type", "target_name") and v is not None:
                    props[k] = v
            rows_data.append({
                "full_type": full_type,
                "source_name": src,
                "target_name": tgt,
                "props": props,
            })

        for i in range(0, len(rows_data), self.UNWIND_BATCH_SIZE):
            batch = rows_data[i:i + self.UNWIND_BATCH_SIZE]
            stmt = CypherStatement(
                statement=(
                    "UNWIND $batch AS row "
                    "MATCH (src {name: row.source_name}) "
                    "MATCH (tgt {name: row.target_name}) "
                    "CALL apoc.merge.relationship(src, row.full_type, {}, row.props, tgt, {}) YIELD rel "
                    "RETURN count(rel) AS created"
                ),
                params={"batch": batch},
                description=(
                    f"CREATE {len(batch)} 条关系（{self.prefix} 前缀）"
                ),
            )
            statements.append(stmt)

        return statements

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _count_rows_in_statements(statements: list[CypherStatement]) -> int:
        """从已生成的 Cypher 语句中统计实际行数（UNWIND batch 中的元素数）。"""
        count = 0
        for stmt in statements:
            batch = stmt.params.get("batch", [])
            if isinstance(batch, list):
                count += len(batch)
        return count

    def _full_label(self, short_label: str) -> str:
        return f"{self.prefix}{short_label}"

    def _full_rel_type(self, short_type: str) -> str:
        return f"{self.prefix}{short_type}"

    def _extract_entity_props(self, row: dict) -> dict:
        """从行数据中提取实体属性：name 必须包含，其余字段放入 props。"""
        props = {}
        for k, v in row.items():
            if k in ("_row", "label"):
                continue
            if v is not None:
                props[k] = v
        # 确保 name 存在
        if "name" not in props:
            props["name"] = ""
        return props
