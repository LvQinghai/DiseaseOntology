"""Neo4j 数据访问层 —— 封装所有原始 Cypher 查询，不包含业务逻辑."""

from neo4j import GraphDatabase, Driver
from backend.config import settings

# 关系类型中文映射
REL_TYPE_LABELS: dict[str, str] = {
    "SUB_CLASS_OF": "子类",
    "MANIFESTS_IN": "症状出现于",
    "TREATS": "治疗",
    "CONTRAINDICATED_WITH": "禁忌",
    "CAN_SUBSTITUTE": "可替代",
    "AFFECTS": "影响部位",
    "HAS_SIDE_EFFECT": "副作用",
}

# 节点类型配色
NODE_COLORS: dict[str, str] = {
    "Disease": "#FF6B6B",
    "Symptom": "#4ECDC4",
    "Drug": "#6C5CE7",
    "BodyPart": "#FECA57",
    "SideEffect": "#A29BFE",
}


class Neo4jRepository:
    """Neo4j 数据访问层"""

    def __init__(self, uri: str, user: str, password: str):
        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()

    def _run(self, cypher: str, **params) -> list[dict]:
        """执行 Cypher 查询并返回字典列表."""
        with self._driver.session() as session:
            result = session.run(cypher, **params)
            return [dict(record) for record in result]

    # ==================== 元数据查询 ====================

    def get_node_labels(self) -> list[dict]:
        """获取所有节点标签及实例数量."""
        return self._run(
            "MATCH (n) RETURN DISTINCT labels(n)[0] AS label, count(*) AS count "
            "ORDER BY count DESC"
        )

    def get_label_properties(self, label: str) -> list[dict]:
        """获取指定标签下所有属性的名称及示例值."""
        records = self._run(
            f"MATCH (n:`{label}`) RETURN n LIMIT 1"
        )
        if not records or "n" not in records[0]:
            return []
        node = records[0]["n"]
        return [
            {"name": key, "sample_value": str(value)[:100] if value is not None else None}
            for key, value in node.items()
        ]

    def get_relationship_types(self) -> list[dict]:
        """获取所有关系类型、源标签、目标标签及数量."""
        return self._run(
            "MATCH (a)-[r]->(b) "
            "RETURN DISTINCT type(r) AS type, "
            "labels(a)[0] AS source_label, "
            "labels(b)[0] AS target_label, "
            "count(*) AS count "
            "ORDER BY type"
        )

    # ==================== 实例查询 ====================

    def get_nodes_by_label(self, label: str, limit: int = 200, offset: int = 0) -> list[dict]:
        """分页获取指定标签的节点实例."""
        return self._run(
            f"MATCH (n:`{label}`) "
            "RETURN elementId(n) AS element_id, labels(n) AS labels, "
            "n.name AS name "
            "ORDER BY n.name "
            "SKIP $offset LIMIT $limit",
            offset=offset, limit=limit,
        )

    def get_root_nodes_by_label(self, label: str, limit: int = 200) -> list[dict]:
        """获取指定标签的根节点（无 SUB_CLASS_OF 父类的顶级节点），含子类计数."""
        return self._run(
            f"MATCH (n:`{label}`) "
            "WHERE NOT (n)-[:SUB_CLASS_OF]->() "
            "OPTIONAL MATCH (child)-[:SUB_CLASS_OF]->(n) "
            "RETURN elementId(n) AS element_id, labels(n) AS labels, "
            "n.name AS name, count(child) AS child_count "
            "ORDER BY n.name "
            "LIMIT $limit",
            limit=limit,
        )

    def get_node_by_id(self, element_id: str) -> dict | None:
        """根据 elementId 获取节点详情."""
        records = self._run(
            "MATCH (n) WHERE elementId(n) = $element_id "
            "RETURN elementId(n) AS element_id, labels(n) AS labels, properties(n) AS properties",
            element_id=element_id,
        )
        return records[0] if records else None

    def get_node_relationships(self, element_id: str) -> list[dict]:
        """获取某节点的所有关系."""
        incoming = self._run(
            "MATCH (source)-[r]->(target) WHERE elementId(target) = $element_id "
            "RETURN type(r) AS type, 'incoming' AS direction, "
            "elementId(source) AS target_element_id, "
            "source.name AS target_name, "
            "labels(source)[0] AS target_label, "
            "properties(r) AS properties",
            element_id=element_id,
        )
        outgoing = self._run(
            "MATCH (source)-[r]->(target) WHERE elementId(source) = $element_id "
            "RETURN type(r) AS type, 'outgoing' AS direction, "
            "elementId(target) AS target_element_id, "
            "target.name AS target_name, "
            "labels(target)[0] AS target_label, "
            "properties(r) AS properties",
            element_id=element_id,
        )
        return incoming + outgoing

    def search_nodes(self, keyword: str, labels: list[str] | None = None) -> list[dict]:
        """模糊搜索节点（按 name 属性 CONTAINS 匹配），keyword 为空时返回全部节点."""
        if not keyword:
            return self._run(
                "MATCH (n) "
                "RETURN elementId(n) AS element_id, n.name AS name, "
                "labels(n) AS labels "
                "ORDER BY n.name "
                "LIMIT 200",
            )
        if labels:
            clauses = " OR ".join([f"n:`{lbl}`" for lbl in labels])
            label_filter = f"AND ({clauses})"
        else:
            label_filter = ""
        return self._run(
            f"MATCH (n) WHERE n.name CONTAINS $keyword {label_filter} "
            "RETURN elementId(n) AS element_id, n.name AS name, "
            "labels(n) AS labels "
            "LIMIT 50",
            keyword=keyword,
        )

    # ==================== 图谱查询 ====================

    def get_all_nodes(self, limit: int = 200) -> list[dict]:
        """获取所有节点（图谱可视化用）."""
        return self._run(
            "MATCH (n) "
            "RETURN elementId(n) AS id, n.name AS label, labels(n)[0] AS type "
            "LIMIT $limit",
            limit=limit,
        )

    def get_all_edges(self, limit: int = 500) -> list[dict]:
        """获取所有边（图谱可视化用）."""
        return self._run(
            "MATCH (a)-[r]->(b) "
            "RETURN elementId(r) AS id, "
            "elementId(a) AS source, elementId(b) AS target, "
            "type(r) AS type "
            "LIMIT $limit",
            limit=limit,
        )

    def get_neighborhood(self, element_id: str, depth: int = 1) -> dict:
        """获取某节点的 N 跳邻居子图."""
        # 使用可变长度路径获取邻域
        nodes = self._run(
            f"MATCH (center)-[r*1..{depth}]-(neighbor) "
            "WHERE elementId(center) = $element_id "
            "RETURN DISTINCT elementId(neighbor) AS id, "
            "neighbor.name AS label, labels(neighbor)[0] AS type",
            element_id=element_id,
        )
        edges = self._run(
            f"MATCH (center)-[r*1..{depth}]-(neighbor) "
            "WHERE elementId(center) = $element_id "
            "MATCH (a)-[rel]-(b) WHERE elementId(a) IN [n IN $node_ids | n] "
            "RETURN DISTINCT elementId(rel) AS id, "
            "elementId(a) AS source, elementId(b) AS target, type(rel) AS type",
            element_id=element_id,
            node_ids=[n["id"] for n in nodes] + [element_id],
        )
        return {"nodes": nodes, "edges": edges}

    def get_path_between(self, source_id: str, target_id: str, max_depth: int = 4) -> dict | None:
        """查找两节点间的最短路径."""
        records = self._run(
            f"MATCH (a) WHERE elementId(a) = $source_id "
            f"MATCH (b) WHERE elementId(b) = $target_id "
            f"MATCH p = shortestPath((a)-[*..{max_depth}]-(b)) "
            "RETURN p",
            source_id=source_id, target_id=target_id,
        )
        if not records:
            return None

        path = records[0]["p"]
        nodes = []
        edges = []
        seen_nodes = set()
        for node in path.nodes:
            nid = node.element_id
            if nid not in seen_nodes:
                seen_nodes.add(nid)
                nodes.append({
                    "id": nid,
                    "label": node.get("name", ""),
                    "type": list(node.labels)[0] if node.labels else "Unknown",
                })
        for rel in path.relationships:
            edges.append({
                "id": rel.element_id,
                "source": rel.start_node.element_id,
                "target": rel.end_node.element_id,
                "type": rel.type,
            })
        return {"nodes": nodes, "edges": edges}

    # ==================== 层级查询 ====================

    def get_subclass_children(self, element_id: str, limit: int = 100) -> list[dict]:
        """获取 SUB_CLASS_OF 子节点（以当前节点为父类的子类节点），含孙类计数."""
        return self._run(
            "MATCH (child)-[:SUB_CLASS_OF]->(parent) "
            "WHERE elementId(parent) = $element_id "
            "OPTIONAL MATCH (grandchild)-[:SUB_CLASS_OF]->(child) "
            "RETURN elementId(child) AS element_id, labels(child) AS labels, "
            "child.name AS name, count(grandchild) AS child_count "
            "ORDER BY child.name "
            "LIMIT $limit",
            element_id=element_id, limit=limit,
        )

    # ==================== 关系查询 ====================

    def get_relationships_by_type(self, rel_type: str, limit: int = 100) -> list[dict]:
        """获取指定关系类型的所有实例."""
        return self._run(
            f"MATCH (a)-[r:`{rel_type}`]->(b) "
            "RETURN elementId(r) AS id, "
            "elementId(a) AS source_id, a.name AS source_name, labels(a)[0] AS source_label, "
            "elementId(b) AS target_id, b.name AS target_name, labels(b)[0] AS target_label, "
            "properties(r) AS properties "
            "LIMIT $limit",
            limit=limit,
        )

    # ==================== 原始查询（供 QueryService 内部使用） ====================

    def execute_cypher(self, cypher: str) -> list[dict]:
        """执行自定义 Cypher 查询.

        ⚠️ 仅内部使用，不对外暴露 API.
        """
        return self._run(cypher)

    # ==================== 实体（节点）写操作 ====================

    def create_node(self, label: str, properties: dict) -> dict:
        """创建指定标签的新节点."""
        return self._run(
            f"CREATE (n:`{label}`) SET n = $props "
            "RETURN elementId(n) AS element_id, labels(n) AS labels, "
            "properties(n) AS properties",
            props=properties,
        )[0]

    def update_node_properties(self, element_id: str, properties: dict) -> dict | None:
        """更新节点属性（合并模式）."""
        records = self._run(
            "MATCH (n) WHERE elementId(n) = $eid "
            "SET n += $props "
            "RETURN elementId(n) AS element_id, labels(n) AS labels, "
            "properties(n) AS properties",
            eid=element_id, props=properties,
        )
        return records[0] if records else None

    def set_node_name(self, element_id: str, name: str) -> dict | None:
        """更新节点名称."""
        records = self._run(
            "MATCH (n) WHERE elementId(n) = $eid "
            "SET n.name = $name "
            "RETURN elementId(n) AS element_id, labels(n) AS labels, "
            "properties(n) AS properties",
            eid=element_id, name=name,
        )
        return records[0] if records else None

    def update_node_label(self, element_id: str, new_label: str) -> dict | None:
        """更新节点标签（替换所有标签为新标签）."""
        # 先移除所有标签，再设置新标签
        node = self.get_node_by_id(element_id)
        if not node:
            return None
        old_labels = node["labels"]
        remove_clause = " ".join(f"REMOVE n:`{lbl}`" for lbl in old_labels)
        self._run(
            f"MATCH (n) WHERE elementId(n) = $eid {remove_clause}",
            eid=element_id,
        )
        records = self._run(
            f"MATCH (n) WHERE elementId(n) = $eid "
            f"SET n:`{new_label}` "
            "RETURN elementId(n) AS element_id, labels(n) AS labels, "
            "properties(n) AS properties",
            eid=element_id,
        )
        return records[0] if records else None

    def delete_node(self, element_id: str, force: bool = False) -> bool:
        """删除节点。force=False 时只删除无关系的节点；force=True 时级联删除所有关系."""
        if force:
            cypher = "MATCH (n) WHERE elementId(n) = $eid DETACH DELETE n RETURN count(n) AS deleted"
        else:
            cypher = "MATCH (n) WHERE elementId(n) = $eid DELETE n RETURN count(n) AS deleted"
        records = self._run(cypher, eid=element_id)
        return records[0].get("deleted", 0) > 0 if records else False

    def get_node_relationships_detail(self, element_id: str) -> list[dict]:
        """获取节点的所有关系详细信息（用于删除前校验）."""
        incoming = self._run(
            "MATCH (source)-[r]->(target) WHERE elementId(target) = $eid "
            "RETURN elementId(r) AS element_id, type(r) AS type, "
            "'incoming' AS direction, "
            "source.name AS other_node_name, "
            "elementId(source) AS other_node_element_id, "
            "labels(source)[0] AS other_node_label",
            eid=element_id,
        )
        outgoing = self._run(
            "MATCH (source)-[r]->(target) WHERE elementId(source) = $eid "
            "RETURN elementId(r) AS element_id, type(r) AS type, "
            "'outgoing' AS direction, "
            "target.name AS other_node_name, "
            "elementId(target) AS other_node_element_id, "
            "labels(target)[0] AS other_node_label",
            eid=element_id,
        )
        return incoming + outgoing

    def get_node_relationship_count(self, element_id: str) -> int:
        """获取节点关联的关系数."""
        records = self._run(
            "MATCH (n)-[r]-() WHERE elementId(n) = $eid "
            "RETURN count(r) AS rel_count",
            eid=element_id,
        )
        return records[0].get("rel_count", 0) if records else 0

    def find_node_by_name(self, name: str, label: str | None = None) -> dict | None:
        """按名称查找节点（精确匹配）."""
        if label:
            records = self._run(
                f"MATCH (n:`{label}`) WHERE n.name = $name "
                "RETURN elementId(n) AS element_id, labels(n) AS labels, "
                "properties(n) AS properties LIMIT 1",
                name=name,
            )
        else:
            records = self._run(
                "MATCH (n) WHERE n.name = $name "
                "RETURN elementId(n) AS element_id, labels(n) AS labels, "
                "properties(n) AS properties LIMIT 1",
                name=name,
            )
        return records[0] if records else None

    # ==================== 属性操作 ====================

    def delete_node_property(self, element_id: str, property_key: str) -> dict | None:
        """删除节点的指定属性."""
        records = self._run(
            "MATCH (n) WHERE elementId(n) = $eid "
            f"SET n.`{property_key}` = null "
            "RETURN elementId(n) AS element_id, labels(n) AS labels, "
            "properties(n) AS properties",
            eid=element_id,
        )
        return records[0] if records else None

    # ==================== 关系写操作 ====================

    def create_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        properties: dict | None = None,
    ) -> dict:
        """在两个节点间创建关系."""
        props = properties or {}
        records = self._run(
            f"MATCH (a), (b) "
            "WHERE elementId(a) = $src AND elementId(b) = $tgt "
            f"CREATE (a)-[r:`{rel_type}`]->(b) SET r = $props "
            "RETURN elementId(r) AS element_id, type(r) AS type, "
            "elementId(a) AS source_id, a.name AS source_name, "
            "elementId(b) AS target_id, b.name AS target_name, "
            "properties(r) AS properties",
            src=source_id, tgt=target_id, props=props,
        )
        return records[0] if records else None

    def update_relationship_properties(self, rel_element_id: str, properties: dict) -> dict | None:
        """更新关系属性."""
        records = self._run(
            "MATCH ()-[r]->() WHERE elementId(r) = $eid "
            "SET r += $props "
            "RETURN elementId(r) AS element_id, type(r) AS type, "
            "elementId(startNode(r)) AS source_id, startNode(r).name AS source_name, "
            "elementId(endNode(r)) AS target_id, endNode(r).name AS target_name, "
            "properties(r) AS properties",
            eid=rel_element_id, props=properties,
        )
        return records[0] if records else None

    def get_relationship_by_id(self, rel_element_id: str) -> dict | None:
        """获取关系详情."""
        records = self._run(
            "MATCH (a)-[r]->(b) WHERE elementId(r) = $eid "
            "RETURN elementId(r) AS element_id, type(r) AS type, "
            "elementId(a) AS source_id, a.name AS source_name, "
            "elementId(b) AS target_id, b.name AS target_name, "
            "properties(r) AS properties",
            eid=rel_element_id,
        )
        return records[0] if records else None

    def update_relationship_full(
        self,
        rel_element_id: str,
        source_id: str | None = None,
        target_id: str | None = None,
        rel_type: str | None = None,
        properties: dict | None = None,
    ) -> dict | None:
        """全量更新关系（源/目标/类型/属性均可改）."""
        old = self.get_relationship_by_id(rel_element_id)
        if not old:
            return None

        new_src = source_id or old["source_id"]
        new_tgt = target_id or old["target_id"]
        new_type = rel_type or old["type"]
        props = properties if properties is not None else old["properties"]

        # 删除旧关系，创建新关系
        self.delete_relationship(rel_element_id)
        return self.create_relationship(new_src, new_tgt, new_type, props)

    def delete_relationship(self, rel_element_id: str) -> bool:
        """删除关系."""
        records = self._run(
            "MATCH ()-[r]->() WHERE elementId(r) = $eid DELETE r "
            "RETURN count(r) AS deleted",
            eid=rel_element_id,
        )
        return records[0].get("deleted", 0) > 0 if records else False

    def find_relationship(
        self, source_id: str, target_id: str, rel_type: str
    ) -> dict | None:
        """查找两个节点间指定类型的关系（用于重复检测）."""
        records = self._run(
            f"MATCH (a)-[r:`{rel_type}`]->(b) "
            "WHERE elementId(a) = $src AND elementId(b) = $tgt "
            "RETURN elementId(r) AS element_id LIMIT 1",
            src=source_id, tgt=target_id,
        )
        return records[0] if records else None

    # ==================== 元数据（编辑用） ====================

    def get_all_labels(self) -> list[str]:
        """获取数据库中所有存在的标签."""
        records = self._run("CALL db.labels()")
        return [r["label"] for r in records]

    def get_all_relationship_type_names(self) -> list[str]:
        """获取所有关系类型名称."""
        records = self._run("CALL db.relationshipTypes()")
        return [r["relationshipType"] for r in records]
