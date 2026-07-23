"""图谱可视化服务."""

from backend.repositories.neo4j_repository import Neo4jRepository, NODE_COLORS, REL_TYPE_LABELS
from backend.models.graph import GraphNode, GraphEdge, GraphData, GraphMeta


class GraphService:
    """图谱可视化服务"""

    def __init__(self, repo: Neo4jRepository):
        self._repo = repo

    def get_overview(self) -> GraphData:
        """获取全量图谱数据."""
        raw_nodes = self._repo.get_all_nodes()
        raw_edges = self._repo.get_all_edges()

        nodes = [
            GraphNode(
                id=n["id"],
                label=n.get("label", ""),
                type=n.get("type", "Unknown"),
                color=NODE_COLORS.get(n.get("type", ""), "#999999"),
            )
            for n in raw_nodes
        ]
        edges = [
            GraphEdge(
                id=e["id"],
                source=e["source"],
                target=e["target"],
                type=e["type"],
                label=REL_TYPE_LABELS.get(e["type"], e["type"]),
            )
            for e in raw_edges
        ]

        return GraphData(
            nodes=nodes,
            edges=edges,
            meta=GraphMeta(total_nodes=len(nodes), total_edges=len(edges)),
        )

    def get_neighborhood(self, element_id: str, depth: int = 1) -> GraphData:
        """获取节点邻域子图."""
        raw = self._repo.get_neighborhood(element_id, depth)

        nodes = [
            GraphNode(
                id=n["id"],
                label=n.get("label", ""),
                type=n.get("type", "Unknown"),
                color=NODE_COLORS.get(n.get("type", ""), "#999999"),
            )
            for n in raw["nodes"]
        ]
        # 加上中心节点本身
        center = self._repo.get_node_by_id(element_id)
        if center:
            label = center["properties"].get("name", "")
            node_type = center["labels"][0] if center["labels"] else "Unknown"
            existing_ids = {n.id for n in nodes}
            if element_id not in existing_ids:
                nodes.append(GraphNode(
                    id=element_id,
                    label=label,
                    type=node_type,
                    color=NODE_COLORS.get(node_type, "#999999"),
                ))

        edges = [
            GraphEdge(
                id=e["id"],
                source=e["source"],
                target=e["target"],
                type=e["type"],
                label=REL_TYPE_LABELS.get(e["type"], e["type"]),
            )
            for e in raw["edges"]
        ]

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

        nodes = [
            GraphNode(
                id=n["id"],
                label=n.get("label", ""),
                type=n.get("type", "Unknown"),
                color=NODE_COLORS.get(n.get("type", ""), "#999999"),
            )
            for n in raw["nodes"]
        ]
        edges = [
            GraphEdge(
                id=e["id"],
                source=e["source"],
                target=e["target"],
                type=e["type"],
                label=REL_TYPE_LABELS.get(e["type"], e["type"]),
            )
            for e in raw["edges"]
        ]
        return GraphData(
            nodes=nodes,
            edges=edges,
            meta=GraphMeta(total_nodes=len(nodes), total_edges=len(edges)),
        )
