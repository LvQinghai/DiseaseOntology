"""v3.0 Neo4j 前缀迁移脚本 —— 标签重命名 + 关系类型重建 + 移除 system_id.

说明：
  - SQLite 初始化（建表 + 种子数据）由 database.py 在启动时自动完成。
  - 本模块仅执行 Neo4j 端的标签/关系前缀迁移。
  - 幂等：检测到 MED_ 标签已存在则跳过。
"""

from neo4j import GraphDatabase

from backend.config import settings

# ---- 标签映射: v2.0 旧标签 → v3.0 新标签 ----
LABEL_MAPPINGS = {
    "Disease":      "MED_Disease",
    "Symptom":      "MED_Symptom",
    "Drug":         "MED_Drug",
    "BodyPart":     "MED_BodyPart",
    "SideEffect":   "MED_SideEffect",
}

# ---- 关系类型映射: v2.0 旧类型 → v3.0 新类型 ----
REL_MAPPINGS = {
    "SUB_CLASS_OF":         "MED_SUB_CLASS_OF",
    "MANIFESTS_IN":         "MED_MANIFESTS_IN",
    "TREATS":               "MED_TREATS",
    "CONTRAINDICATED_WITH": "MED_CONTRAINDICATED_WITH",
    "CAN_SUBSTITUTE":       "MED_CAN_SUBSTITUTE",
    "AFFECTS":              "MED_AFFECTS",
    "HAS_SIDE_EFFECT":      "MED_HAS_SIDE_EFFECT",
}

DEFAULT_PREFIX = "MED_"


def run_migration() -> bool:
    """执行 Neo4j v2.0 → v3.0 标签/关系前缀迁移.

    Returns:
        True 如果执行了迁移，False 如果已迁移过（跳过）。
    """
    uri = settings.neo4j_uri
    user = settings.neo4j_user
    password = settings.neo4j_password

    if not uri:
        print("⚠️  未配置 Neo4j URI，跳过 Neo4j 迁移")
        return False

    driver = GraphDatabase.driver(uri, auth=(user, password))

    try:
        with driver.session() as session:

            # ---- 检查是否已迁移 ----
            check = session.run(
                "MATCH (n:MED_Disease) RETURN n LIMIT 1"
            )
            if check.single():
                print("✅ Neo4j 已使用 MED_ 前缀，跳过迁移")
                return False

            print("🚀 开始 Neo4j v2.0 → v3.0 前缀迁移 (MED_)")

            # ---- 步骤 1: 迁移关系类型（必须在标签迁移之前执行） ----
            print("\n📌 步骤 1/3: 迁移关系类型...")
            total_rels = 0
            for old_type, new_type in REL_MAPPINGS.items():
                result = session.run(f"""
                    MATCH (a)-[r:`{old_type}`]->(b)
                    CREATE (a)-[r_new:`{new_type}`]->(b)
                    SET r_new = properties(r)
                    DELETE r
                    RETURN count(r_new) AS migrated
                """)
                count = result.single()["migrated"]
                total_rels += count
                if count > 0:
                    print(f"  {old_type:25s} → {new_type:25s} ({count} 条)")

            print(f"  共迁移 {total_rels} 条关系")

            # ---- 步骤 2: 重命名节点标签 ----
            print("\n📌 步骤 2/3: 重命名节点标签...")
            total_nodes = 0
            for old_label, new_label in LABEL_MAPPINGS.items():
                result = session.run(f"""
                    MATCH (n:`{old_label}`)
                    SET n:`{new_label}`
                    REMOVE n:`{old_label}`
                    RETURN count(n) AS migrated
                """)
                count = result.single()["migrated"]
                total_nodes += count
                if count > 0:
                    print(f"  {old_label:15s} → {new_label:15s} ({count} 个)")

            print(f"  共迁移 {total_nodes} 个节点")

            # ---- 步骤 3: 移除 system_id 属性 ----
            print("\n📌 步骤 3/3: 移除 system_id 属性...")
            result = session.run("""
                MATCH (n)
                WHERE n.system_id IS NOT NULL
                REMOVE n.system_id
                RETURN count(n) AS cleaned
            """)
            cleaned = result.single()["cleaned"]
            if cleaned > 0:
                print(f"  已从 {cleaned} 个节点移除 system_id 属性")
            else:
                print("  无需要清理的 system_id 属性")

            print(f"\n🎉 Neo4j 迁移完成: prefix={DEFAULT_PREFIX}, "
                  f"{total_nodes} 节点, {total_rels} 关系")
            return True

    finally:
        driver.close()
