"""本体浏览服务 —— 聚合本体元数据."""

from backend.repositories.neo4j_repository import Neo4jRepository, REL_TYPE_LABELS
from backend.models.ontology import (
    PropertyDetail,
    NodeTypeInfo,
    NodeInstance,
    NodeDetail,
    RelationshipItem,
    OntologyTree,
    RelationshipCatalogItem,
    SearchResult,
)


class OntologyService:
    """本体浏览服务"""

    def __init__(self, repo: Neo4jRepository):
        self._repo = repo

    def get_tree(self) -> OntologyTree:
        """构建完整本体树.
        
        对于 Disease 等标签：若根节点存在子类（如 '疾病' 节点），
        则将其子类提升到根层级，去除冗余的聚合层级。
        """
        # 节点类型
        label_data = self._repo.get_node_labels()
        node_types: list[NodeTypeInfo] = []
        for item in label_data:
            label = item["label"]
            props = self._repo.get_label_properties(label)
            instances_raw = self._repo.get_root_nodes_by_label(label, limit=100)

            # 展开聚合节点：若根节点有子类，将其子类提升到根层级
            instances: list[NodeInstance] = []
            for inst in instances_raw:
                child_count = inst.get("child_count", 0)
                if child_count > 0:
                    # 聚合节点（如 '疾病'）—— 用其子类替代
                    children_raw = self._repo.get_subclass_children(
                        inst["element_id"], limit=100
                    )
                    for child in children_raw:
                        instances.append(NodeInstance(
                            element_id=child["element_id"],
                            name=child.get("name", ""),
                            labels=child.get("labels", []),
                            child_count=child.get("child_count", 0),
                        ))
                else:
                    # 叶子根节点（如 '严重主动脉瓣狭窄'、'青霉素过敏'）
                    instances.append(NodeInstance(
                        element_id=inst["element_id"],
                        name=inst.get("name", ""),
                        labels=inst.get("labels", []),
                        child_count=0,
                    ))

            node_types.append(NodeTypeInfo(
                label=label,
                count=item["count"],
                properties=[PropertyDetail(name=p["name"], sample_value=p["sample_value"])
                            for p in props],
                instances=instances,
            ))

        # 关系类型
        rel_data = self._repo.get_relationship_types()
        rel_types: list[RelationshipCatalogItem] = []
        for item in rel_data:
            raw_type = item["type"]
            rel_types.append(RelationshipCatalogItem(
                type=raw_type,
                count=item["count"],
                source_labels=[item["source_label"]] if item.get("source_label") else [],
                target_labels=[item["target_label"]] if item.get("target_label") else [],
                description=REL_TYPE_LABELS.get(raw_type, raw_type),
            ))

        return OntologyTree(node_types=node_types, relationship_types=rel_types)

    def get_node_detail(self, element_id: str) -> NodeDetail | None:
        """获取节点完整详情."""
        node = self._repo.get_node_by_id(element_id)
        if not node:
            return None

        relationships = self._repo.get_node_relationships(element_id)
        incoming = [
            RelationshipItem(
                type=r["type"], direction=r["direction"],
                target_element_id=r["target_element_id"],
                target_name=r.get("target_name", ""),
                target_label=r.get("target_label", ""),
                properties=r.get("properties", {}),
            )
            for r in relationships if r["direction"] == "incoming"
        ]
        outgoing = [
            RelationshipItem(
                type=r["type"], direction=r["direction"],
                target_element_id=r["target_element_id"],
                target_name=r.get("target_name", ""),
                target_label=r.get("target_label", ""),
                properties=r.get("properties", {}),
            )
            for r in relationships if r["direction"] == "outgoing"
        ]

        return NodeDetail(
            element_id=node["element_id"],
            labels=node["labels"],
            properties=node.get("properties", {}),
            incoming_relationships=incoming,
            outgoing_relationships=outgoing,
        )

    def get_relationship_catalog(self) -> list[RelationshipCatalogItem]:
        """获取关系类型目录."""
        rel_data = self._repo.get_relationship_types()
        return [
            RelationshipCatalogItem(
                type=item["type"],
                count=item["count"],
                source_labels=[item["source_label"]] if item.get("source_label") else [],
                target_labels=[item["target_label"]] if item.get("target_label") else [],
                description=REL_TYPE_LABELS.get(item["type"], item["type"]),
            )
            for item in rel_data
        ]

    def get_subclass_children(self, element_id: str) -> list[NodeInstance]:
        """获取节点的 SUB_CLASS_OF 子类."""
        children = self._repo.get_subclass_children(element_id)
        return [
            NodeInstance(
                element_id=c["element_id"],
                name=c.get("name", ""),
                labels=c.get("labels", []),
                child_count=c.get("child_count", 0),
            )
            for c in children
        ]

    def search(self, keyword: str) -> list[SearchResult]:
        """全局模糊搜索."""
        results = self._repo.search_nodes(keyword)
        return [
            SearchResult(
                element_id=r["element_id"],
                name=r.get("name", ""),
                labels=r.get("labels", []),
                match_field="name",
            )
            for r in results
        ]
