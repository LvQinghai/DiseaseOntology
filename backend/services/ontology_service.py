"""本体浏览服务 —— 聚合本体元数据（v3.0: prefix 驱动）."""

from backend.repositories.neo4j_repository import Neo4jRepository, REL_TYPE_LABELS
from backend.utils.label_utils import strip_prefix
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

    def get_tree(self, prefix: str) -> OntologyTree:
        """构建完整本体树。prefix 用于过滤当前系统的标签和关系类型。"""
        # 节点类型
        label_data = self._repo.get_node_labels(prefix)
        node_types: list[NodeTypeInfo] = []
        for item in label_data:
            full_label = item["label"]
            short_label = strip_prefix(full_label, prefix)
            props = self._repo.get_label_properties(short_label, prefix)
            instances_raw = self._repo.get_root_nodes_by_label(
                short_label, prefix, limit=100
            )

            # 展开聚合节点：若根节点有子类，将其子类提升到根层级
            instances: list[NodeInstance] = []
            for inst in instances_raw:
                child_count = inst.get("child_count", 0)
                if child_count > 0:
                    children_raw = self._repo.get_subclass_children(
                        inst["element_id"], prefix, limit=100
                    )
                    for child in children_raw:
                        instances.append(NodeInstance(
                            element_id=child["element_id"],
                            name=child.get("name", ""),
                            labels=child.get("labels", []),
                            child_count=child.get("child_count", 0),
                        ))
                else:
                    instances.append(NodeInstance(
                        element_id=inst["element_id"],
                        name=inst.get("name", ""),
                        labels=inst.get("labels", []),
                        child_count=0,
                    ))

            # 对外展示用短标签名
            node_types.append(NodeTypeInfo(
                label=short_label,
                count=item["count"],
                properties=[PropertyDetail(name=p["name"], sample_value=p["sample_value"])
                            for p in props],
                instances=instances,
            ))

        # 关系类型（对外剥离前缀）
        rel_data = self._repo.get_relationship_types(prefix)
        rel_types: list[RelationshipCatalogItem] = []
        for item in rel_data:
            raw_type = item["type"]
            short_type = strip_prefix(raw_type, prefix)
            rel_types.append(RelationshipCatalogItem(
                type=short_type,
                count=item["count"],
                source_labels=[strip_prefix(l, prefix)
                               for l in item.get("source_labels", [])],
                target_labels=[strip_prefix(l, prefix)
                               for l in item.get("target_labels", [])],
                description=REL_TYPE_LABELS.get(short_type, raw_type),
            ))

        return OntologyTree(node_types=node_types, relationship_types=rel_types)

    def get_node_detail(self, element_id: str, prefix: str = "") -> NodeDetail | None:
        """获取节点完整详情. prefix 非空时仅返回同系统关系."""
        node = self._repo.get_node_by_id(element_id)
        if not node:
            return None

        relationships = self._repo.get_node_relationships(element_id, prefix)
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

        props = node.get("properties", {})
        node_name = props.get("name", "") or node.get("name", "")
        return NodeDetail(
            element_id=node["element_id"],
            name=node_name,
            labels=node["labels"],
            properties=props,
            incoming_relationships=incoming,
            outgoing_relationships=outgoing,
        )

    def get_relationship_catalog(self, prefix: str) -> list[RelationshipCatalogItem]:
        """获取关系类型目录（对外剥离前缀）。"""
        rel_data = self._repo.get_relationship_types(prefix)
        return [
            RelationshipCatalogItem(
                type=strip_prefix(item["type"], prefix),
                count=item["count"],
                source_labels=[strip_prefix(l, prefix)
                               for l in item.get("source_labels", [])],
                target_labels=[strip_prefix(l, prefix)
                               for l in item.get("target_labels", [])],
                description=REL_TYPE_LABELS.get(
                    strip_prefix(item["type"], prefix), item["type"]
                ),
            )
            for item in rel_data
        ]

    def get_subclass_children(self, element_id: str, prefix: str) -> list[NodeInstance]:
        """获取节点的 SUB_CLASS_OF 子类."""
        children = self._repo.get_subclass_children(element_id, prefix)
        return [
            NodeInstance(
                element_id=c["element_id"],
                name=c.get("name", ""),
                labels=c.get("labels", []),
                child_count=c.get("child_count", 0),
            )
            for c in children
        ]

    def search(self, keyword: str, prefix: str) -> list[SearchResult]:
        """全局模糊搜索。."""
        results = self._repo.search_nodes(keyword, prefix)
        return [
            SearchResult(
                element_id=r["element_id"],
                name=r.get("name", ""),
                labels=r.get("labels", []),
                match_field="name",
            )
            for r in results
        ]
