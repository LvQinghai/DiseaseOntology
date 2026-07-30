"""Neo4j 数据访问层 —— 封装所有原始 Cypher 查询，不包含业务逻辑.

v3.0: 基于 prefix 的多系统前缀隔离方案。
      - 所有系统级方法接受 prefix（如 "MED_"），不再使用 system_id。
      - System 元数据管理已移至 SQLite，本模块不再包含系统 CRUD 方法。
"""
from __future__ import annotations

from neo4j import GraphDatabase, Driver
from backend.config import settings

# 关系类型中文映射（短名 → 中文）
REL_TYPE_LABELS: dict[str, str] = {
    "SUB_CLASS_OF": "子类",
    "MANIFESTS_IN": "症状出现于",
    "TREATS": "治疗",
    "CONTRAINDICATED_WITH": "禁忌",
    "CAN_SUBSTITUTE": "可替代",
    "AFFECTS": "影响部位",
    "HAS_SIDE_EFFECT": "副作用",
}

# 节点类型配色（短名 → 色值）—— 工业专业调色板
NODE_COLORS: dict[str, str] = {
    "Disease": "#f5222d",
    "Symptom": "#fa8c16",
    "Drug": "#1890ff",
    "BodyPart": "#52c41a",
    "SideEffect": "#722ed1",
    "Department": "#eb2f96",
    "Student": "#13c2c2",
    "Teacher": "#2f54eb",
    "Subject": "#faad14",
    "Course": "#a0d911",
    "Patient": "#f759ab",
    "Hospital": "#722ed1",
    "Doctor": "#1677ff",
    "Test": "#bfbfbf",
    "Exam": "#ff7a45",
    "Treatment": "#52c41a",
    "Prescription": "#1890ff",
    "Diagnosis": "#fa541c",
}

# 备用调色板（用于不在 NODE_COLORS 中的未知类型动态分配）
_FALLBACK_COLORS: list[str] = [
    "#f5222d", "#fa8c16", "#1890ff", "#52c41a", "#722ed1",
    "#eb2f96", "#13c2c2", "#2f54eb", "#faad14", "#a0d911",
    "#f759ab", "#1677ff", "#ff7a45", "#fa541c", "#9254de",
    "#36cfc9", "#d4380d", "#0958d9", "#389e0d", "#c41d7f",
]


def get_node_color(node_type: str) -> str:
    """获取节点类型的颜色。如果在映射表中则直接返回，否则基于哈希动态分配。"""
    short = node_type.split("_")[-1] if "_" in node_type else node_type
    if short in NODE_COLORS:
        return NODE_COLORS[short]
    # 动态分配：基于类型名哈希从备用调色板中选取
    # 使用稳定哈希，避免 Python 进程重启后同一类型颜色变化。
    idx = sum((position + 1) * ord(char) for position, char in enumerate(short)) % len(_FALLBACK_COLORS)
    return _FALLBACK_COLORS[idx]


class Neo4jRepository:
    """Neo4j 数据访问层."""

    def __init__(self, uri: str, user: str, password: str):
        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()

    def _run(self, cypher: str, **params) -> list[dict]:
        """执行 Cypher 查询并返回字典列表."""
        with self._driver.session() as session:
            result = session.run(cypher, **params)
            return [dict(record) for record in result]

    def _run_write(self, cypher: str, params: dict) -> list[dict]:
        """执行写操作（使用写入事务）."""
        with self._driver.session() as session:
            result = session.execute_write(lambda tx: list(tx.run(cypher, params)))
            return [dict(record) for record in result]

    # ═══════════════════════════════════════════
    # 元数据查询（prefix 隔离）
    # ═══════════════════════════════════════════

    def get_node_labels(self, prefix: str) -> list[dict]:
        """获取当前系统内所有节点标签及实例数量."""
        return self._run(
            "MATCH (n) "
            "WHERE ANY(label IN labels(n) WHERE label STARTS WITH $prefix) "
            "WITH [l IN labels(n) WHERE l STARTS WITH $prefix][0] AS label, n "
            "RETURN label, count(*) AS count "
            "ORDER BY count DESC",
            prefix=prefix,
        )

    def get_label_properties(self, label: str, prefix: str) -> list[dict]:
        """获取指定标签下所有属性的名称及示例值。label 为短标签名."""
        full_label = f"{prefix}{label}"
        records = self._run(
            f"MATCH (n:`{full_label}`) RETURN n LIMIT 1"
        )
        if not records or "n" not in records[0]:
            return []
        node = records[0]["n"]
        return [
            {"name": key, "sample_value": str(value)[:100] if value is not None else None}
            for key, value in node.items()
        ]

    def get_relationship_types(self, prefix: str) -> list[dict]:
        """获取当前系统内所有关系类型、源标签列表、目标标签列表及数量.

        按关系类型聚合：同一类型用于多种标签组合时（如 MANIFESTS_IN 同时
        连接 Symptom→Disease 和 SideEffect→Disease），合并为一条，
        源/目标标签以列表形式返回，避免树状目录出现重复条目。
        """
        return self._run(
            "MATCH (a)-[r]->(b) "
            "WHERE type(r) STARTS WITH $prefix "
            "AND ANY(l IN labels(a) WHERE l STARTS WITH $prefix) "
            "AND ANY(l IN labels(b) WHERE l STARTS WITH $prefix) "
            "WITH type(r) AS type, "
            "[l IN labels(a) WHERE l STARTS WITH $prefix][0] AS source_label, "
            "[l IN labels(b) WHERE l STARTS WITH $prefix][0] AS target_label "
            "RETURN type, "
            "collect(DISTINCT source_label) AS source_labels, "
            "collect(DISTINCT target_label) AS target_labels, "
            "count(*) AS count "
            "ORDER BY type",
            prefix=prefix,
        )

    # ═══════════════════════════════════════════
    # 实例查询（prefix 隔离）
    # ═══════════════════════════════════════════

    def get_nodes_by_label(
        self, label: str, prefix: str, limit: int = 200, offset: int = 0
    ) -> list[dict]:
        """分页获取指定标签的节点实例。label 为短标签名."""
        full_label = f"{prefix}{label}"
        return self._run(
            f"MATCH (n:`{full_label}`) "
            "RETURN elementId(n) AS element_id, labels(n) AS labels, "
            "n.name AS name "
            "ORDER BY n.name "
            "SKIP $offset LIMIT $limit",
            offset=offset, limit=limit,
        )

    def get_root_nodes_by_label(
        self, label: str, prefix: str, limit: int = 200
    ) -> list[dict]:
        """获取指定标签的根节点（无 SUB_CLASS_OF 父类的顶级节点），含子类计数."""
        full_label = f"{prefix}{label}"
        sub_class_rel = f"{prefix}SUB_CLASS_OF"
        return self._run(
            f"MATCH (n:`{full_label}`) "
            f"WHERE NOT (n)-[:`{sub_class_rel}`]->() "
            f"OPTIONAL MATCH (child)-[:`{sub_class_rel}`]->(n) "
            "RETURN elementId(n) AS element_id, labels(n) AS labels, "
            "n.name AS name, count(child) AS child_count "
            "ORDER BY n.name "
            "LIMIT $limit",
            limit=limit,
        )

    def search_nodes(
        self, keyword: str, prefix: str,
        labels: list[str] | None = None
    ) -> list[dict]:
        """模糊搜索节点（按 name 属性 CONTAINS 匹配），限定当前系统.
         keyword 为空时返回全部节点.
         labels 为短标签名列表.
        """
        prefix_filter = "ANY(l IN labels(n) WHERE l STARTS WITH $prefix)"

        if not keyword:
            return self._run(
                f"MATCH (n) WHERE {prefix_filter} "
                "RETURN elementId(n) AS element_id, n.name AS name, "
                "labels(n) AS labels "
                "ORDER BY n.name "
                "LIMIT 200",
                prefix=prefix,
            )

        if labels:
            full_labels = [f"{prefix}{l}" for l in labels]
            clauses = " OR ".join([f"n:`{lbl}`" for lbl in full_labels])
            label_filter = f"AND ({clauses})"
        else:
            label_filter = ""

        return self._run(
            f"MATCH (n) WHERE {prefix_filter} AND n.name CONTAINS $keyword {label_filter} "
            "RETURN elementId(n) AS element_id, n.name AS name, "
            "labels(n) AS labels "
            "LIMIT 50",
            prefix=prefix, keyword=keyword,
        )

    # ═══════════════════════════════════════════
    # 节点查询（与 system 无关 —— 通过 elementId 操作）
    # ═══════════════════════════════════════════

    def get_node_by_id(self, element_id: str) -> dict | None:
        """根据 elementId 获取节点详情."""
        records = self._run(
            "MATCH (n) WHERE elementId(n) = $element_id "
            "RETURN elementId(n) AS element_id, labels(n) AS labels, properties(n) AS properties",
            element_id=element_id,
        )
        return records[0] if records else None

    def get_node_relationships(self, element_id: str, prefix: str = "") -> list[dict]:
        """获取某节点的所有关系（按 type+direction+target 去重）.

        prefix 非空时仅返回同系统关系，防止跨系统数据泄露。
        """
        if prefix:
            incoming = self._run(
                "MATCH (source)-[r]->(target) WHERE elementId(target) = $element_id "
                "AND type(r) STARTS WITH $prefix "
                "RETURN type(r) AS type, 'incoming' AS direction, "
                "elementId(source) AS target_element_id, "
                "source.name AS target_name, "
                "[l IN labels(source) WHERE l STARTS WITH $prefix][0] AS target_label, "
                "properties(r) AS properties",
                element_id=element_id, prefix=prefix,
            )
            outgoing = self._run(
                "MATCH (source)-[r]->(target) WHERE elementId(source) = $element_id "
                "AND type(r) STARTS WITH $prefix "
                "RETURN type(r) AS type, 'outgoing' AS direction, "
                "elementId(target) AS target_element_id, "
                "target.name AS target_name, "
                "[l IN labels(target) WHERE l STARTS WITH $prefix][0] AS target_label, "
                "properties(r) AS properties",
                element_id=element_id, prefix=prefix,
            )
        else:
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
        all_rels = incoming + outgoing
        # 去重：同一 (type, direction, target_name) 只保留一条
        # 避免 Neo4j 中重复关系导致前端展示多次
        seen: set = set()
        unique: list[dict] = []
        for r in all_rels:
            key = (r.get("type", ""), r.get("direction", ""), r.get("target_name", ""))
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique

    # ═══════════════════════════════════════════
    # 图谱查询（prefix 隔离）
    # ═══════════════════════════════════════════

    def get_all_nodes(self, prefix: str, limit: int = 200) -> list[dict]:
        """获取当前系统内所有节点（图谱可视化用）."""
        return self._run(
            "MATCH (n) "
            "WHERE ANY(label IN labels(n) WHERE label STARTS WITH $prefix) "
            "WITH n, [l IN labels(n) WHERE l STARTS WITH $prefix][0] AS node_type "
            "RETURN elementId(n) AS id, n.name AS label, node_type AS type "
            "LIMIT $limit",
            prefix=prefix, limit=limit,
        )

    def get_all_edges(self, prefix: str, limit: int = 500) -> list[dict]:
        """获取当前系统内所有边（图谱可视化用）."""
        return self._run(
            "MATCH (a)-[r]->(b) "
            "WHERE type(r) STARTS WITH $prefix "
            "AND ANY(label IN labels(a) WHERE label STARTS WITH $prefix) "
            "AND ANY(label IN labels(b) WHERE label STARTS WITH $prefix) "
            "RETURN elementId(r) AS id, "
            "elementId(a) AS source, elementId(b) AS target, "
            "type(r) AS type "
            "LIMIT $limit",
            prefix=prefix, limit=limit,
        )

    def get_neighborhood(self, element_id: str, prefix: str, depth: int = 1) -> dict:
        """获取某节点的 N 跳邻居子图（仅限同 prefix 系统）."""
        # 1) 查邻居节点：按 prefix 过滤 label，防止跨系统
        nodes = self._run(
            f"MATCH (center)-[r*1..{depth}]-(neighbor) "
            "WHERE elementId(center) = $element_id "
            "AND ANY(label IN labels(neighbor) WHERE label STARTS WITH $prefix) "
            "RETURN DISTINCT elementId(neighbor) AS id, "
            "neighbor.name AS label, "
            "[l IN labels(neighbor) WHERE l STARTS WITH $prefix][0] AS type",
            element_id=element_id, prefix=prefix,
        )
        # 2) 查邻居间的边：直接在 node_ids 集合内查边，按 prefix 过滤
        #    （不再在变长路径 r 上用 type()，那会导致 Cypher 报错使 edges 为空）
        node_ids = [n["id"] for n in nodes] + [element_id]
        edges = self._run(
            "MATCH (a)-[rel]-(b) "
            "WHERE elementId(a) IN $node_ids "
            "AND elementId(b) IN $node_ids "
            "AND type(rel) STARTS WITH $prefix "
            "AND ANY(label IN labels(a) WHERE label STARTS WITH $prefix) "
            "AND ANY(label IN labels(b) WHERE label STARTS WITH $prefix) "
            "RETURN DISTINCT elementId(rel) AS id, "
            "elementId(a) AS source, elementId(b) AS target, type(rel) AS type",
            prefix=prefix, node_ids=node_ids,
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

    # ═══════════════════════════════════════════
    # 层级查询（prefix 隔离）
    # ═══════════════════════════════════════════

    def get_subclass_children(self, element_id: str, prefix: str,
                              limit: int = 100) -> list[dict]:
        """获取 SUB_CLASS_OF 子节点（以当前节点为父类的子类节点），含孙类计数."""
        sub_class_rel = f"{prefix}SUB_CLASS_OF"
        return self._run(
            f"MATCH (child)-[:`{sub_class_rel}`]->(parent) "
            "WHERE elementId(parent) = $element_id "
            f"OPTIONAL MATCH (grandchild)-[:`{sub_class_rel}`]->(child) "
            "RETURN elementId(child) AS element_id, labels(child) AS labels, "
            "child.name AS name, count(grandchild) AS child_count "
            "ORDER BY child.name "
            "LIMIT $limit",
            element_id=element_id, limit=limit,
        )

    # ═══════════════════════════════════════════
    # 关系查询（prefix 隔离）
    # ═══════════════════════════════════════════

    def get_relationships_by_type(
        self, rel_type: str, prefix: str, limit: int = 100
    ) -> list[dict]:
        """获取当前系统内某关系类型的所有实例。rel_type 为短类型名."""
        full_type = f"{prefix}{rel_type}"
        return self._run(
            f"MATCH (a)-[r:`{full_type}`]->(b) "
            "RETURN elementId(r) AS id, "
            "elementId(a) AS source_id, a.name AS source_name, "
            "labels(a)[0] AS source_label, "
            "elementId(b) AS target_id, b.name AS target_name, "
            "labels(b)[0] AS target_label, "
            "properties(r) AS properties "
            "LIMIT $limit",
            limit=limit,
        )

    def get_relationship_instances(self, rel_type: str, prefix: str,
                                   limit: int = 100) -> list[dict]:
        """获取关系实例摘要（编辑器用）。rel_type 为短类型名."""
        full_type = f"{prefix}{rel_type}"
        results = self._run(
            f"MATCH (a)-[r:`{full_type}`]->(b) "
            "RETURN elementId(r) AS element_id, "
            "elementId(a) AS source_id, "
            "a.name AS source_name, labels(a)[0] AS source_label, "
            "elementId(b) AS target_id, "
            "b.name AS target_name, labels(b)[0] AS target_label "
            "ORDER BY a.name "
            "LIMIT $limit",
            limit=limit,
        )
        # 去重：同一 (source_name, target_name) 只保留一条
        seen: set = set()
        unique: list[dict] = []
        for r in results:
            key = (r.get("source_name", ""), r.get("target_name", ""))
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique

    # ═══════════════════════════════════════════
    # 原始查询（供 QueryService 内部使用）
    # ═══════════════════════════════════════════

    def execute_cypher(self, cypher: str) -> list[dict]:
        """执行自定义 Cypher 查询.

        ⚠️ 仅内部使用，不对外暴露 API.
        """
        return self._run(cypher)

    # ═══════════════════════════════════════════
    # 实体（节点）写操作（prefix 驱动）
    # ═══════════════════════════════════════════

    def create_node(self, label: str, properties: dict, prefix: str) -> dict:
        """创建指定标签的新节点。label 为短标签名，prefix 用于拼接完整标签."""
        full_label = f"{prefix}{label}"
        return self._run(
            f"CREATE (n:`{full_label}`) SET n = $props "
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

    def update_node_label(self, element_id: str, new_label: str, prefix: str) -> dict | None:
        """更新节点标签（替换所有标签为新标签）。new_label 为短标签名."""
        node = self.get_node_by_id(element_id)
        if not node:
            return None
        old_labels = node["labels"]
        remove_clause = " ".join(f"REMOVE n:`{lbl}`" for lbl in old_labels)
        self._run(
            f"MATCH (n) WHERE elementId(n) = $eid {remove_clause}",
            eid=element_id,
        )
        full_label = f"{prefix}{new_label}"
        records = self._run(
            f"MATCH (n) WHERE elementId(n) = $eid "
            f"SET n:`{full_label}` "
            "RETURN elementId(n) AS element_id, labels(n) AS labels, "
            "properties(n) AS properties",
            eid=element_id,
        )
        return records[0] if records else None

    def delete_node(self, element_id: str, force: bool = False) -> bool:
        """删除节点。force=False 仅删无关系节点；force=True 级联删除."""
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

    def find_node_by_name(self, name: str, label: str | None = None,
                          prefix: str | None = None) -> dict | None:
        """按名称精确查找节点。限定 prefix 时仅查询当前系统的节点。label 为短标签名."""
        if label and prefix:
            full_label = f"{prefix}{label}"
            records = self._run(
                f"MATCH (n:`{full_label}`) WHERE n.name = $name "
                "RETURN elementId(n) AS element_id, labels(n) AS labels, "
                "properties(n) AS properties LIMIT 1",
                name=name,
            )
        elif prefix:
            records = self._run(
                "MATCH (n) WHERE n.name = $name "
                "AND ANY(l IN labels(n) WHERE l STARTS WITH $prefix) "
                "RETURN elementId(n) AS element_id, labels(n) AS labels, "
                "properties(n) AS properties LIMIT 1",
                name=name, prefix=prefix,
            )
        elif label:
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

    # ═══════════════════════════════════════════
    # 属性操作
    # ═══════════════════════════════════════════

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

    # ═══════════════════════════════════════════
    # 关系写操作（prefix 驱动）
    # ═══════════════════════════════════════════

    def create_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        properties: dict | None = None,
        prefix: str | None = None,
    ) -> dict:
        """在两个节点间创建关系。rel_type 为短类型名，prefix 用于拼接完整类型."""
        full_type = f"{prefix}{rel_type}" if prefix else rel_type
        props = properties or {}
        records = self._run(
            f"MATCH (a), (b) "
            "WHERE elementId(a) = $src AND elementId(b) = $tgt "
            f"CREATE (a)-[r:`{full_type}`]->(b) SET r = $props "
            "RETURN elementId(r) AS element_id, type(r) AS type, "
            "elementId(a) AS source_id, a.name AS source_name, "
            "elementId(b) AS target_id, b.name AS target_name, "
            "properties(r) AS properties",
            src=source_id, tgt=target_id, props=props,
        )
        return records[0] if records else None

    def update_relationship_properties(self, rel_element_id: str,
                                       properties: dict) -> dict | None:
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
        self, source_id: str, target_id: str, rel_type: str,
        prefix: str | None = None,
    ) -> dict | None:
        """查找两个节点间指定类型的关系（用于重复检测）。rel_type 为短类型名."""
        full_type = f"{prefix}{rel_type}" if prefix else rel_type
        records = self._run(
            f"MATCH (a)-[r:`{full_type}`]->(b) "
            "WHERE elementId(a) = $src AND elementId(b) = $tgt "
            "RETURN elementId(r) AS element_id LIMIT 1",
            src=source_id, tgt=target_id,
        )
        return records[0] if records else None

    # ═══════════════════════════════════════════
    # 元数据（编辑用，prefix 隔离）
    # ═══════════════════════════════════════════

    def get_all_labels(self, prefix: str) -> list[str]:
        """获取当前系统中所有存在的标签（完整标签名）."""
        records = self._run(
            "MATCH (n) "
            "WHERE ANY(label IN labels(n) WHERE label STARTS WITH $prefix) "
            "RETURN DISTINCT [l IN labels(n) WHERE l STARTS WITH $prefix][0] AS label "
            "ORDER BY label",
            prefix=prefix,
        )
        return [r["label"] for r in records]

    def get_all_relationship_type_names(self, prefix: str) -> list[str]:
        """获取当前系统中所有关系类型名称（完整类型名）."""
        records = self._run(
            "MATCH ()-[r]->() "
            "WHERE type(r) STARTS WITH $prefix "
            "RETURN DISTINCT type(r) AS relationshipType "
            "ORDER BY relationshipType",
            prefix=prefix,
        )
        return [r["relationshipType"] for r in records]

    # ═══════════════════════════════════════════
    # 冲突检测（v3.5 验证器用）
    # ═══════════════════════════════════════════

    def get_node_by_name(self, name: str, label: str) -> dict | None:
        """按名称和标签查找实体。"""
        records = self._run(
            f"MATCH (n:`{label}` {{name: $name}}) RETURN properties(n) AS properties",
            name=name,
        )
        return records[0] if records else None

    def get_relationship_by_names(
        self, source_name: str, target_name: str, full_type: str
    ) -> dict | None:
        """按源、目标、类型查找关系。"""
        records = self._run(
            "MATCH (src {name: $source_name})-[r]->(tgt {name: $target_name}) "
            "WHERE type(r) = $full_type "
            "RETURN elementId(r) AS elementId, properties(r) AS properties",
            source_name=source_name,
            target_name=target_name,
            full_type=full_type,
        )
        return records[0] if records else None

    def get_all_nodes_by_prefix(self, prefix: str) -> list[dict]:
        """获取指定 prefix 下所有节点（备份用）。"""
        records = self._run(
            "MATCH (n) WHERE ANY(label IN labels(n) WHERE label STARTS WITH $prefix) "
            "RETURN elementId(n) AS elementId, labels(n) AS labels, properties(n) AS properties",
            prefix=prefix,
        )
        return [dict(r) for r in records]

    def get_all_relationships_by_prefix(self, prefix: str) -> list[dict]:
        """获取指定 prefix 下所有关系（备份用）。"""
        records = self._run(
            "MATCH ()-[r]->() WHERE type(r) STARTS WITH $prefix "
            "RETURN elementId(r) AS elementId, type(r) AS type, "
            "elementId(startNode(r)) AS startNodeElementId, "
            "elementId(endNode(r)) AS endNodeElementId, "
            "properties(r) AS properties",
            prefix=prefix,
        )
        return [dict(r) for r in records]

    # ═══════════════════════════════════════════
    # 批量写入（v3.0 导入引擎用，prefix 驱动）
    # ═══════════════════════════════════════════

    def batch_create_nodes(self, nodes: list[dict], prefix: str) -> int:
        """批量创建节点（UNWIND + APOC merge，按 name 去重）。nodes: [{label: 短名, name, ...properties}]."""
        if not nodes:
            return 0
        result = self._run_write(
            "UNWIND $nodes AS row "
            "CALL apoc.merge.node([row.full_label], {name: row.name}, row.props, {}) YIELD node "
            "RETURN count(node) AS created",
            {"nodes": [
                {
                    "full_label": f"{prefix}{n['label']}",
                    "name": n["name"],
                    "props": {"name": n["name"], **(n.get("properties", {}))},
                }
                for n in nodes
            ]},
        )
        return result[0]["created"] if result else 0

    def batch_create_relationships(self, rels: list[dict], prefix: str) -> int:
        """批量创建关系（UNWIND + APOC merge，动态类型，按端点+类型去重，仅限同 prefix 系统）。

        rels: [{type: 短名, source_name, target_name, ...props}].
        """
        if not rels:
            return 0
        result = self._run_write(
            "UNWIND $rels AS row "
            "MATCH (src {name: row.source_name}) "
            "WHERE ANY(label IN labels(src) WHERE label STARTS WITH $prefix) "
            "MATCH (tgt {name: row.target_name}) "
            "WHERE ANY(label IN labels(tgt) WHERE label STARTS WITH $prefix) "
            "CALL apoc.merge.relationship(src, row.full_type, {}, row.props, tgt, {}) YIELD rel "
            "RETURN count(rel) AS created",
            {"rels": [
                {
                    "full_type": f"{prefix}{r['type']}",
                    "source_name": r["source_name"],
                    "target_name": r["target_name"],
                    "props": r.get("props", {}),
                }
                for r in rels
            ], "prefix": prefix},
        )
        return result[0]["created"] if result else 0

    # ═══════════════════════════════════════════
    # 系统清理（v3.0: 按 prefix 删除所有业务数据）
    # ═══════════════════════════════════════════

    def get_relation_types_by_prefix(self, prefix: str) -> list[str]:
        """v3.6: 获取指定 prefix 下的所有关系类型名称（去重，如 ['TREATS', 'HAS_SIDE_EFFECT']）。"""
        try:
            result = self._run(
                "MATCH ()-[r]->() "
                "WHERE type(r) STARTS WITH $prefix "
                "RETURN DISTINCT type(r) AS rel_type "
                "ORDER BY rel_type",
                prefix=prefix,
            )
            return [row["rel_type"] for row in result]
        except Exception:
            return []

    def get_system_stats(self, prefix: str) -> dict:
        """获取指定前缀系统的详细统计信息（用于删除前展示）。"""
        # 节点标签及数量
        node_labels = self._run(
            "MATCH (n) "
            "WHERE ANY(label IN labels(n) WHERE label STARTS WITH $prefix) "
            "WITH [l IN labels(n) WHERE l STARTS WITH $prefix][0] AS label, count(*) AS cnt "
            "RETURN label, cnt ORDER BY cnt DESC",
            prefix=prefix,
        )
        # 关系类型及数量
        rel_types = self._run(
            "MATCH ()-[r]->() WHERE type(r) STARTS WITH $prefix "
            "RETURN type(r) AS rel_type, count(*) AS cnt "
            "ORDER BY cnt DESC",
            prefix=prefix,
        )
        # 总节点数
        total_nodes = self.count_system_nodes(prefix)
        # 总关系数
        total_rels = self.count_system_relationships(prefix)
        return {
            "node_count": total_nodes,
            "relationship_count": total_rels,
            "node_labels": [{"label": r["label"], "count": r["cnt"]} for r in node_labels],
            "relationship_types": [{"type": r["rel_type"], "count": r["cnt"]} for r in rel_types],
        }

    def delete_system_data(self, prefix: str) -> dict:
        """删除指定前缀系统的所有节点和关系.

        注意：此方法仅删除 Neo4j 业务数据，SQLite 系统记录由调用方处理。
        使用"先计数再删除"模式，确保返回准确的删除数量。
        """
        # 先统计（只读查询）
        rel_total = self.count_system_relationships(prefix)
        node_total = self.count_system_nodes(prefix)

        # 删除关系（写操作，不依赖 RETURN count）
        if rel_total > 0:
            self._run_write(
                "MATCH ()-[r]->() WHERE type(r) STARTS WITH $prefix DELETE r",
                {"prefix": prefix},
            )

        # 删除节点（DETACH DELETE 会清理残留关系）
        if node_total > 0:
            self._run_write(
                "MATCH (n) "
                "WHERE ANY(label IN labels(n) WHERE label STARTS WITH $prefix) "
                "DETACH DELETE n",
                {"prefix": prefix},
            )

        return {
            "deleted_nodes": node_total,
            "deleted_relationships": rel_total,
        }

    def count_system_nodes(self, prefix: str) -> int:
        """统计当前系统的节点数."""
        records = self._run(
            "MATCH (n) "
            "WHERE ANY(label IN labels(n) WHERE label STARTS WITH $prefix) "
            "RETURN count(n) AS cnt",
            prefix=prefix,
        )
        return records[0]["cnt"] if records else 0

    def count_system_relationships(self, prefix: str) -> int:
        """统计当前系统的关系数."""
        records = self._run(
            "MATCH ()-[r]->() WHERE type(r) STARTS WITH $prefix "
            "RETURN count(r) AS cnt",
            prefix=prefix,
        )
        return records[0]["cnt"] if records else 0
