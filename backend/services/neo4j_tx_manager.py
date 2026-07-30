"""
Layer 4: Neo4j 事务管理器（备份 / 执行 / 回滚）

功能:
- 写入前自动创建数据快照（按 Prefix 范围导出）
- 在事务中执行一批 Cypher 语句
- 验证写入结果
- 支持从快照回滚
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from backend.repositories.neo4j_repository import Neo4jRepository
from backend.services.cypher_generator import CypherBatch, CypherStatement


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class BackupSnapshot:
    """备份快照"""
    snapshot_id: str
    prefix: str
    created_at: str              # ISO 8601
    node_count: int              # 快照时节点数
    relationship_count: int      # 快照时关系数
    nodes_backup: list[dict] = field(default_factory=list)
    relationships_backup: list[dict] = field(default_factory=list)


@dataclass
class ExecuteResult:
    """执行结果"""
    success: bool
    entities_created: int = 0
    relationships_created: int = 0
    snapshot_id: str | None = None
    backup_available: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    message: str = ""


# ---------------------------------------------------------------------------
# 事务管理器
# ---------------------------------------------------------------------------

class Neo4jTransactionManager:
    """Neo4j 事务管理器"""

    BACKUP_DIR = "backend/data/backups"

    def __init__(self, repo: Neo4jRepository):
        self.repo = repo
        os.makedirs(self.BACKUP_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def execute_with_backup(
        self, cypher_batch: CypherBatch, prefix: str,
    ) -> ExecuteResult:
        """带备份的批量执行流程：备份 → 写入 → 验证。

        Args:
            cypher_batch: 待执行的 CypherBatch
            prefix: 系统前缀
        Returns:
            ExecuteResult（含 snapshot_id 供回滚）
        """
        errors: list[str] = []

        # 1. 创建备份
        snapshot = None
        try:
            snapshot = self.create_backup(prefix)
        except Exception as e:
            return ExecuteResult(
                success=False,
                errors=[f"导入已取消，备份失败: {e}"],
                message="导入已取消：无法创建 Neo4j 导入前备份",
            )

        # 2. 实体写入
        entity_created = 0
        for stmt in cypher_batch.entity_statements:
            try:
                result = self.repo._run_write(stmt.statement, stmt.params)
                created = result[0].get("created", 0) if result else 0
                entity_created += created
            except Exception as e:
                errors.append(f"实体写入失败 [{stmt.description}]: {e}")

        # 3. 关系写入
        rel_created = 0
        for stmt in cypher_batch.relationship_statements:
            try:
                result = self.repo._run_write(stmt.statement, stmt.params)
                created = result[0].get("created", 0) if result else 0
                rel_created += created
            except Exception as e:
                errors.append(f"关系写入失败 [{stmt.description}]: {e}")

        # 4. 验证
        warnings: list[str] = []
        if not errors:
            actual_nodes = self.repo.count_system_nodes(prefix)
            actual_rels = self.repo.count_system_relationships(prefix)
            if entity_created != cypher_batch.entity_count:
                warnings.append(
                    f"实体写入数量偏差: 预期 {cypher_batch.entity_count}, "
                    f"实际 {entity_created}（可能含空标签行被跳过）"
                )
            if rel_created != cypher_batch.relationship_count:
                warnings.append(
                    f"关系写入数量偏差: 预期 {cypher_batch.relationship_count}, "
                    f"实际 {rel_created}（可能含空字段行被跳过）"
                )

        success = len(errors) == 0
        if success and entity_created == 0 and cypher_batch.entity_count > 0:
            success = False
            errors.append("所有实体写入均失败，请检查数据格式")
        if success and rel_created == 0 and cypher_batch.relationship_count > 0:
            warnings.append("关系均未写入（可能源/目标节点不存在）")

        success = len(errors) == 0
        rollback_warning = ""
        if not success and snapshot is not None:
            try:
                rollback_result = self.restore_from_backup(snapshot.snapshot_id)
                if rollback_result.get("success"):
                    rollback_warning = "；失败导入已自动回滚"
                else:
                    rollback_warning = f"；自动回滚失败: {rollback_result.get('message', '未知错误')}"
            except Exception as rollback_error:
                rollback_warning = f"；自动回滚异常: {rollback_error}"
            warnings.append(rollback_warning.lstrip("；"))

        message = (
            f"导入完成: {entity_created} 个实体, {rel_created} 条关系"
            if success
            else f"导入失败: {'; '.join(errors[:3])}{rollback_warning}"
        )

        return ExecuteResult(
            success=success,
            entities_created=entity_created,
            relationships_created=rel_created,
            snapshot_id=snapshot.snapshot_id if snapshot else None,
            backup_available=snapshot is not None,
            errors=errors,
            warnings=warnings,
            message=message,
        )

    def create_backup(self, prefix: str) -> BackupSnapshot:
        """创建指定 prefix 范围的备份快照。"""
        now = datetime.now()
        snapshot_id = f"{now.strftime('%Y%m%d_%H%M%S')}_{prefix}"

        # 导出节点数据
        nodes = self.repo.get_all_nodes_by_prefix(prefix)
        relationships = self.repo.get_all_relationships_by_prefix(prefix)

        snapshot = BackupSnapshot(
            snapshot_id=snapshot_id,
            prefix=prefix,
            created_at=now.isoformat(),
            node_count=len(nodes),
            relationship_count=len(relationships),
            nodes_backup=self._serialize_backup_data(nodes),
            relationships_backup=self._serialize_backup_data(relationships),
        )

        # 存储到文件
        filepath = os.path.join(self.BACKUP_DIR, f"{snapshot_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self._snapshot_to_dict(snapshot), f, ensure_ascii=False, indent=2, default=str)

        return snapshot

    def restore_from_backup(self, snapshot_id: str) -> dict:
        """从备份快照恢复数据。

        恢复流程:
        1. 读取快照文件
        2. 删除当前 prefix 下所有数据
        3. 从备份重建节点（建立 old_elementId → name 映射）
        4. 从备份重建关系（通过 name 匹配，因为 elementId 在重建后已变）
        """
        filepath = os.path.join(self.BACKUP_DIR, f"{snapshot_id}.json")
        if not os.path.exists(filepath):
            return {"success": False, "message": f"快照 {snapshot_id} 不存在"}

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        prefix = data.get("prefix", "")
        if not prefix:
            return {"success": False, "message": "快照数据无效: 缺少 prefix"}

        # 兼容新旧备份格式的键名
        nodes_backup = data.get("nodes_backup") or data.get("nodes") or []
        rels_backup = data.get("relationships_backup") or data.get("relationships") or []

        try:
            # 1. 删除当前数据
            delete_result = self.repo.delete_system_data(prefix)
            deleted_nodes = delete_result.get("deleted_nodes", 0)
            deleted_rels = delete_result.get("deleted_relationships", 0)

            # 提前建立 elementId → name 映射（用于后续关系匹配）
            id_to_name: dict[str, str] = {}
            for node in nodes_backup:
                eid = node.get("elementId", "")
                name = node.get("properties", {}).get("name", "")
                if eid and name:
                    id_to_name[eid] = name

            # 2. 重建节点
            nodes_restored = 0
            for node in nodes_backup:
                labels = node.get("labels", [])
                props = node.get("properties", {})
                if labels and props.get("name"):
                    self.repo._run_write(
                        "CALL apoc.merge.node($labels, {name: $name}, $props, {}) YIELD node "
                        "RETURN count(node) AS created",
                        {"labels": labels, "props": props, "name": props.get("name", "")},
                    )
                    nodes_restored += 1

            # 3. 重建关系（通过 name 匹配源/目标节点）
            rels_restored = 0
            rel_errors: list[str] = []
            for rel in rels_backup:
                rtype = rel.get("type", "")
                start_id = rel.get("startNodeElementId", "")
                end_id = rel.get("endNodeElementId", "")
                props = rel.get("properties", {})

                # 通过 elementId 查找原始节点名称
                start_name = id_to_name.get(start_id, "")
                end_name = id_to_name.get(end_id, "")
                if not rtype or not start_name or not end_name:
                    continue

                result = self.repo._run_write(
                    "MATCH (src {name: $start_name}) "
                    "MATCH (tgt {name: $end_name}) "
                    "CALL apoc.merge.relationship(src, $rtype, {}, $props, tgt, {}) YIELD rel "
                    "RETURN count(rel) AS created",
                    {
                        "start_name": start_name,
                        "end_name": end_name,
                        "rtype": rtype,
                        "props": props,
                    },
                )
                created = result[0].get("created", 0) if result else 0
                if created:
                    rels_restored += created
                else:
                    rel_errors.append(
                        f"[{rtype}] {start_name} -> {end_name}: 未找到节点"
                    )

            # v3.5.1: 清理 name 匹配可能产生的重复关系
            # （当备份中存在同名节点时，MERGE 会创建多条）
            if rel_errors:
                # 有未恢复的关系，记录 warning
                pass

            return {
                "success": True,
                "message": (
                    f"已从快照 {snapshot_id} 恢复: "
                    f"{nodes_restored} 个节点, {rels_restored} 条关系"
                ),
                "restored_nodes": nodes_restored,
                "restored_relationships": rels_restored,
                "deleted_before_restore": {"nodes": deleted_nodes, "relationships": deleted_rels},
                "rel_errors": rel_errors if rel_errors else [],
            }

        except Exception as e:
            return {"success": False, "message": f"回滚失败: {e}"}

    def list_backups(self) -> list[dict]:
        """列出所有备份快照。"""
        backups: list[dict] = []
        if not os.path.isdir(self.BACKUP_DIR):
            return backups
        for fname in sorted(os.listdir(self.BACKUP_DIR), reverse=True):
            if not fname.endswith(".json"):
                continue
            filepath = os.path.join(self.BACKUP_DIR, fname)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                backups.append({
                    "snapshot_id": data.get("snapshot_id", fname.replace(".json", "")),
                    "prefix": data.get("prefix", ""),
                    "created_at": data.get("created_at", ""),
                    "node_count": data.get("node_count", 0),
                    "relationship_count": data.get("relationship_count", 0),
                    "file_size": os.path.getsize(filepath),
                })
            except Exception:
                continue
        return backups

    def delete_backup(self, snapshot_id: str) -> bool:
        """删除指定备份。"""
        filepath = os.path.join(self.BACKUP_DIR, f"{snapshot_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _snapshot_to_dict(self, snapshot: BackupSnapshot) -> dict:
        return {
            "snapshot_id": snapshot.snapshot_id,
            "prefix": snapshot.prefix,
            "created_at": snapshot.created_at,
            "node_count": snapshot.node_count,
            "relationship_count": snapshot.relationship_count,
            "nodes_backup": snapshot.nodes_backup,
            "relationships_backup": snapshot.relationships_backup,
        }

    @staticmethod
    def _serialize_backup_data(data: list[dict]) -> list[dict]:
        """确保备份数据可 JSON 序列化。"""
        import datetime as dt
        result = []
        for item in data:
            clean = {}
            for k, v in item.items():
                if isinstance(v, (dt.date, dt.datetime)):
                    clean[k] = v.isoformat()
                elif isinstance(v, bytes):
                    clean[k] = v.decode("utf-8", errors="replace")
                else:
                    try:
                        json.dumps(v)
                        clean[k] = v
                    except (TypeError, ValueError):
                        clean[k] = str(v)
            result.append(clean)
        return result
