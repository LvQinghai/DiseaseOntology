"""系统管理服务 —— v3.0: 基于 SQLAlchemy SQLite 存储元数据."""

import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.database import get_session
from backend.models.system import (
    SystemModel,
    RelationSemanticModel,
    SystemInfo,
    RelationSemanticInfo,
    UpsertRelationSemanticRequest,
    SystemSemanticsResponse,
)

# 保留前缀列表（不可用于业务系统）
_RESERVED_PREFIXES = {"SYS_", "META_", "ADMIN_"}

# 前缀格式验证正则：3位大写字母
_PREFIX_PATTERN = re.compile(r'^[A-Z]{3}$')


def normalize_prefix(raw: str) -> str:
    """将用户输入的前缀标准化为带下划线的格式。

    规则：
    - 去除首尾空白，转为大写
    - 如果未以下划线结尾，自动追加 "_"
    - 验证基础部分为 3 位大写字母（在调用方进行）

    示例：
        "car"   → "CAR_"
        "MED"   → "MED_"
        "CAR_"  → "CAR_"
    """
    prefix = raw.strip().upper()
    if prefix.endswith("_"):
        prefix = prefix.rstrip("_")
        # 再次标准化加回下划线
    if not prefix:
        raise ValueError("前缀不能为空")
    if not _PREFIX_PATTERN.match(prefix):
        raise ValueError(f"前缀格式错误：'{raw}'，必须为 3 位大写字母（如 'CAR'、'MED'）")
    return prefix + "_"


class SystemService:
    """系统管理服务 —— 所有系统元数据读写均通过 SQLite"""

    # ───────────── 查询 ─────────────

    def get_all_systems(self) -> list[SystemInfo]:
        """获取所有系统列表（从 SQLite）。"""
        session = get_session()
        try:
            rows = session.query(SystemModel).order_by(
                SystemModel.system_id.asc()
            ).all()
            return [self._to_info(r) for r in rows]
        finally:
            session.close()

    def get_system(self, system_id: str) -> SystemInfo | None:
        """获取单个系统信息。"""
        session = get_session()
        try:
            row = session.query(SystemModel).filter_by(
                system_id=system_id
            ).first()
            return self._to_info(row) if row else None
        finally:
            session.close()

    def get_prefix(self, system_id: str) -> str:
        """根据 system_id 获取 prefix（用于 Router 层解析）。"""
        system = self.get_system(system_id)
        if not system:
            raise ValueError(f"系统 '{system_id}' 不存在")
        return system.prefix

    # ───────────── 写操作 ─────────────

    def create_system(
        self, name: str, description: str = "",
        prefix: str = "", import_source: str = "manual",
    ) -> SystemInfo:
        """创建新系统（写入 SQLite）。

        - 自动分配 prefix（如果用户未指定或 prefix 冲突）。
        - 自动生成唯一 system_id。
        """
        session = get_session()
        try:
            existing_prefixes = {
                r.prefix for r in session.query(SystemModel.prefix).all()
            }
            if not prefix:
                prefix = self._generate_prefix(name, existing_prefixes)
            else:
                prefix = normalize_prefix(prefix)  # 自动追加下划线 + 格式验证
                if prefix in existing_prefixes:
                    raise ValueError(f"前缀 '{prefix}' 已被其他系统使用")
                if prefix in _RESERVED_PREFIXES:
                    raise ValueError(f"前缀 '{prefix}' 为系统保留前缀，不可用于业务系统")

            # 生成 system_id：prefix（去掉末尾下划线）+ "_" + 生成时间
            prefix_clean = prefix.rstrip('_')
            system_id = f"{prefix_clean}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            now = datetime.now(timezone.utc).isoformat()
            model = SystemModel(
                system_id=system_id,
                name=name.strip(),
                description=description,
                prefix=prefix,
                import_source=import_source,
                created_at=now,
                updated_at=now,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            return self._to_info(model)
        finally:
            session.close()

    def delete_system(self, system_id: str) -> bool:
        """删除系统（SQLite 删记录）。"""
        session = get_session()
        try:
            row = session.query(SystemModel).filter_by(
                system_id=system_id
            ).first()
            if not row:
                return False
            session.delete(row)
            session.commit()
            return True
        finally:
            session.close()

    def update_counts(self, system_id: str,
                      node_count: int, relationship_count: int) -> None:
        """更新系统节点/关系统计。"""
        session = get_session()
        try:
            row = session.query(SystemModel).filter_by(
                system_id=system_id
            ).first()
            if row:
                row.node_count = node_count
                row.relationship_count = relationship_count
                row.updated_at = datetime.now(timezone.utc).isoformat()
                session.commit()
        finally:
            session.close()

    # ───────────── 工具 ─────────────

    def _to_info(self, model: SystemModel) -> SystemInfo:
        """ORM 模型 → Pydantic 模型。"""
        return SystemInfo(
            system_id=model.system_id,
            prefix=model.prefix,
            name=model.name,
            description=model.description or "",
            node_count=model.node_count or 0,
            relationship_count=model.relationship_count or 0,
            created_at=model.created_at or "",
            updated_at=model.updated_at or "",
            import_source=model.import_source or "manual",
        )

    @staticmethod
    def _slugify(name: str) -> str:
        """将系统名称转为合法的 system_id。"""
        slug = name.strip().lower()
        slug = re.sub(r'\s+', '_', slug)
        slug = re.sub(r'[^a-z0-9_]', '', slug)
        return slug or "unnamed_system"

    @staticmethod
    def _generate_prefix(name: str, existing: set[str]) -> str:
        """根据系统名称自动生成唯一前缀。

        规则：
        1. 提取英文单词首字母（大写）
        2. 加下划线结尾
        3. 冲突时递增序号
        """
        chars = re.findall(r'[A-Za-z]', name)
        if chars:
            base = "".join([c.upper() for c in chars[:3]])
        else:
            base = "KG"  # Knowledge Graph fallback

        prefix = f"{base}_"
        if prefix not in existing and prefix not in _RESERVED_PREFIXES:
            return prefix

        for i in range(2, 20):
            alt = f"{base}{i}_"
            if alt not in existing and alt not in _RESERVED_PREFIXES:
                return alt

        # 极端兜底
        import string, random
        while True:
            prefix = "".join(random.choices(string.ascii_uppercase, k=3)) + "_"
            if prefix not in existing and prefix not in _RESERVED_PREFIXES:
                return prefix

    # ═══════════════════════════════════════════
    # v3.6: 关系语义 CRUD
    # ═══════════════════════════════════════════

    def get_relation_semantics(self, prefix: str) -> list[RelationSemanticInfo]:
        """获取指定系统的全部关系语义配置。"""
        session = get_session()
        try:
            rows = (
                session.query(RelationSemanticModel)
                .filter_by(prefix=prefix)
                .order_by(RelationSemanticModel.rel_type)
                .all()
            )
            return [self._to_semantic_info(r) for r in rows]
        finally:
            session.close()

    def get_relation_semantic(
        self, prefix: str, rel_type: str
    ) -> RelationSemanticInfo | None:
        """获取单条关系语义。"""
        session = get_session()
        try:
            row = (
                session.query(RelationSemanticModel)
                .filter_by(prefix=prefix, rel_type=rel_type)
                .first()
            )
            return self._to_semantic_info(row) if row else None
        finally:
            session.close()

    def upsert_relation_semantic(
        self, prefix: str, req: UpsertRelationSemanticRequest,
    ) -> RelationSemanticInfo:
        """创建或更新一条关系语义（按 prefix + rel_type 唯一）。"""
        session = get_session()
        try:
            row = (
                session.query(RelationSemanticModel)
                .filter_by(prefix=prefix, rel_type=req.rel_type)
                .first()
            )
            now = datetime.now(timezone.utc).isoformat()
            if row:
                row.display_name = req.display_name
                row.description = req.description
                row.source_hint = req.source_hint
                row.target_hint = req.target_hint
                row.cardinality = req.cardinality
                row.symmetry = req.symmetry
                row.transitivity = req.transitivity
                row.updated_at = now
            else:
                row = RelationSemanticModel(
                    prefix=prefix,
                    rel_type=req.rel_type,
                    display_name=req.display_name,
                    description=req.description,
                    source_hint=req.source_hint,
                    target_hint=req.target_hint,
                    cardinality=req.cardinality,
                    symmetry=req.symmetry,
                    transitivity=req.transitivity,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            session.commit()
            session.refresh(row)
            return self._to_semantic_info(row)
        finally:
            session.close()

    def delete_relation_semantic(self, prefix: str, rel_type: str) -> bool:
        """删除一条关系语义。"""
        session = get_session()
        try:
            row = (
                session.query(RelationSemanticModel)
                .filter_by(prefix=prefix, rel_type=rel_type)
                .first()
            )
            if not row:
                return False
            session.delete(row)
            session.commit()
            return True
        finally:
            session.close()

    def get_semantics_for_query(self, prefix: str) -> SystemSemanticsResponse:
        """为 QueryService 提供完整的语义上下文。"""
        system = self.get_system_by_prefix(prefix)
        domain_desc = system.description if system else ""
        semantics = self.get_relation_semantics(prefix)
        return SystemSemanticsResponse(
            prefix=prefix,
            domain_description=domain_desc,
            semantics=semantics,
        )

    def get_system_by_prefix(self, prefix: str) -> SystemInfo | None:
        """通过 prefix 查找系统（用于 QueryService 语义获取）。"""
        session = get_session()
        try:
            row = (
                session.query(SystemModel)
                .filter_by(prefix=prefix)
                .first()
            )
            return self._to_info(row) if row else None
        finally:
            session.close()

    def init_semantics_from_neo4j(
        self, prefix: str, relation_types: list[str]
    ) -> int:
        """从 Neo4j 扫描的关系类型自动初始化语义配置。

        仅对不存在的进行初始化，已有配置的不覆盖。
        返回新初始化的数量。
        """
        existing = {
            s.rel_type for s in self.get_relation_semantics(prefix)
        }
        initialized = 0
        for rt in relation_types:
            if rt in existing:
                continue
            self.upsert_relation_semantic(
                prefix,
                UpsertRelationSemanticRequest(
                    rel_type=rt,
                    display_name=rt,     # 默认用原名
                    description="",
                ),
            )
            initialized += 1
        return initialized

    def _to_semantic_info(
        self, model: RelationSemanticModel
    ) -> RelationSemanticInfo:
        return RelationSemanticInfo(
            id=model.id,
            prefix=model.prefix or "",
            rel_type=model.rel_type or "",
            display_name=model.display_name or "",
            description=model.description or "",
            source_hint=model.source_hint or "",
            target_hint=model.target_hint or "",
            cardinality=model.cardinality or "",
            symmetry=model.symmetry or "",
            transitivity=model.transitivity or "",
            created_at=model.created_at or "",
            updated_at=model.updated_at or "",
        )
