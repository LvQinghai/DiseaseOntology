"""图谱可视化服务（v3.0: prefix 驱动）."""

from backend.repositories.neo4j_repository import Neo4jRepository, get_node_color
from backend.utils.label_utils import strip_prefix
from backend.models.graph import GraphNode, GraphEdge, GraphData, GraphMeta


class GraphService:
    """图谱可视化服务"""

    def __init__(self, repo: Neo4jRepository, system_svc=None):
        self._repo = repo
        self._system_svc = system_svc

    # ── 关系标签：从用户配置的语义中读取 display_name ──────────

    def _get_rel_labels(self, prefix: str) -> dict[str, str]:
        """从 SQLite 读取该系统的关系语义 display_name 映射。

        返回 {短类型名: display_name}，如 {"AFFECTS": "影响部位"}。
        未配置语义的关系类型不在映射中，调用方用 short_type 兜底。
        """
        if not self._system_svc or not prefix:
            return {}
        try:
            sem = self._system_svc.get_semantics_for_query(prefix)
            if sem and sem.semantics:
                return {
                    s.rel_type: s.display_name
                    for s in sem.semantics
                    if s.display_name
                }
        except Exception:
            pass
        return {}

    @staticmethod
    def _extract_prefix(rel_type: str) -> str:
        """从关系类型提取 prefix（如 'IT_AFFECTS' → 'IT_'）。"""
        idx = rel_type.find("_")
        return rel_type[:idx + 1] if idx != -1 else ""

    # ── 图谱查询 ──────────────────────────────────────────

    def get_overview(self, prefix: str) -> GraphData:
        """获取全量图谱数据."""
        raw_nodes = self._repo.get_all_nodes(prefix)
        raw_edges = self._repo.get_all_edges(prefix)
        node_ids = {n.get("id") for n in raw_nodes if n.get("id")}
        # 防止异常/历史数据中的关系端点在前端被 vis-network 创建为默认节点
        raw_edges = [
            e for e in raw_edges
            if e.get("id")
            and e.get("source") in node_ids
            and e.get("target") in node_ids
        ]
        rel_labels = self._get_rel_labels(prefix)

        nodes = []
        for n in raw_nodes:
            node_type = n.get("type", "Unknown")
            short_type = strip_prefix(node_type, prefix)
            nodes.append(GraphNode(
                id=n["id"],
                label=n.get("label", ""),
                type=short_type,  # 对外展示用短标签名
                color=get_node_color(short_type),
            ))

        edges = []
        for e in raw_edges:
            edge_type = e["type"]
            short_type = strip_prefix(edge_type, prefix)
            edges.append(GraphEdge(
                id=e["id"],
                source=e["source"],
                target=e["target"],
                type=short_type,
                label=rel_labels.get(short_type, short_type),
            ))

        return GraphData(
            nodes=nodes,
            edges=edges,
            meta=GraphMeta(total_nodes=len(nodes), total_edges=len(edges)),
        )

    def get_neighborhood(self, element_id: str, prefix: str, depth: int = 1) -> GraphData:
        """获取节点邻域子图（同系统内）."""
        raw = self._repo.get_neighborhood(element_id, prefix, depth)

        # 使用传入的 prefix 查询关系语义（不再覆盖为空）
        rel_labels = self._get_rel_labels(prefix)

        nodes = []
        for n in raw["nodes"]:
            node_type = n.get("type", "Unknown")
            short_type = strip_prefix(node_type, prefix) if prefix else node_type
            nodes.append(GraphNode(
                id=n["id"],
                label=n.get("label", ""),
                type=short_type,
                color=get_node_color(short_type),
            ))
        # 加上中心节点本身
        center = self._repo.get_node_by_id(element_id)
        if center:
            label = center["properties"].get("name", "")
            # 按 prefix 过滤 label，防止跨系统
            sys_labels = [l for l in center["labels"] if l.startswith(prefix)]
            node_type = sys_labels[0] if sys_labels else "Unknown"
            existing_ids = {n.id for n in nodes}
            if element_id not in existing_ids:
                short_type = strip_prefix(node_type, prefix) if prefix else node_type
                nodes.append(GraphNode(
                    id=element_id,
                    label=label,
                    type=short_type,
                    color=get_node_color(short_type),
                ))

        edges = []
        for e in raw["edges"]:
            etype = e["type"]
            short = strip_prefix(etype, prefix) if prefix else etype
            edges.append(GraphEdge(
                id=e["id"],
                source=e["source"],
                target=e["target"],
                type=short,
                label=rel_labels.get(short, short),
            ))

        return GraphData(
            nodes=nodes,
            edges=edges,
            meta=GraphMeta(total_nodes=len(nodes), total_edges=len(edges)),
        )

    def get_path(self, source_id: str, target_id: str) -> GraphData | None:
        """获取两节点间的最短路径."""
        raw = self._repo.get_path_between(source_id, target_id)
        if not raw:
            return None

        # 从边类型提取 prefix，查询关系语义
        prefix = ""
        if raw["edges"]:
            prefix = self._extract_prefix(raw["edges"][0]["type"])
        rel_labels = self._get_rel_labels(prefix)

        nodes = []
        for n in raw["nodes"]:
            node_type = n.get("type", "Unknown")
            short_type = strip_prefix(node_type, prefix) if prefix else node_type
            nodes.append(GraphNode(
                id=n["id"],
                label=n.get("label", ""),
                type=short_type,
                color=get_node_color(short_type),
            ))
        edges = []
        for e in raw["edges"]:
            etype = e["type"]
            short = strip_prefix(etype, prefix) if prefix else etype
            edges.append(GraphEdge(
                id=e["id"],
                source=e["source"],
                target=e["target"],
                type=short,
                label=rel_labels.get(short, short),
            ))
        return GraphData(
            nodes=nodes,
            edges=edges,
            meta=GraphMeta(total_nodes=len(nodes), total_edges=len(edges)),
        )
