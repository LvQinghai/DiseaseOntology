import os
import sys
from langchain_community.graphs import Neo4jGraph
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

# 自定义 API 配置
API_BASE = "https://aicopilot.goldwind.com.cn:3213/v1"
API_KEY = "sk-53kl7zp0NWu6i15q8FAQT48W4NJbBHviZweYfc9Ih8KnUhVr"

# 禁用 SSL 验证（如证书不受信任时需要）
os.environ["SSL_CERT_FILE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""

# 1. 连接 Neo4j（自动提取 Schema）
graph = Neo4jGraph(
    url="bolt://localhost:7687",
    username="neo4j",
    password="MyNeo4j2026"
)
print("✅ Neo4j 连接成功")
print(f"   Schema 预览:\n{graph.schema}\n")

# 2. 初始化 LLM（使用自定义 API）
llm = ChatOpenAI(
    temperature=0,
    model="glm-5.2",
    openai_api_key=API_KEY,
    openai_api_base=API_BASE,
)

# 3. 自定义 Cypher 生成提示词（强调关系方向）
CYPHER_GENERATION_TEMPLATE = """任务：将用户问题转换为 Neo4j Cypher 查询语句。

图数据库 Schema:
{schema}

⚠️ 重要规则：
0. 数据库中所有数据均为中文。如果用户用英文提问，必须先把关键实体名（疾病、症状、药物、部位）翻译成中文，再写入 Cypher 查询。例如 "cold" → "感冒", "stomach" → "胃"。
0-1. 节点匹配永远使用 `CONTAINS` 而不是 `=`，因为用户输入可能是真实名称的一部分。例如 `WHERE d.name CONTAINS '感冒'` 而非 `{{name: '感冒'}}`。
1. 关系方向必须严格匹配 Schema 中定义的方向。切勿反向查询。
2. 常见查询模式：
   - 某疾病的症状 → `MATCH (s:Symptom)-[:MANIFESTS_IN]->(d:Disease)`
   - 某身体部位的疾病 → `MATCH (d:Disease)-[:AFFECTS]->(b:BodyPart)`
   - 某药物的副作用 → `MATCH (d:Drug)-[:HAS_SIDE_EFFECT]->(se:SideEffect)`
   - 某类疾病的子类 → `MATCH (child:Disease)-[:SUB_CLASS_OF]->(parent:Disease)`
3. 节点之间关系的含义
    -SUB_CLASS_OF 传递性 → 用 [:SUB_CLASS_OF*1..3] 展开
    -CONTRAINDICATED_WITH 硬约束 → 用 NOT 排除
    -CAN_SUBSTITUTE 对称性 → 双向查询
    -MANIFESTS_IN 多值 → 一症状对应多病，按匹配数排序
    -综合推理 → 用 WITH 串联多步
4. 如果问题涉及某"大类"的疾病（如"消化系统疾病""呼吸系统疾病"），必须通过 `SUB_CLASS_OF` 递归查找所有子类疾病，再查找子类的症状。不能只查大类本身（大类本身没有症状）。
5. 对于层次结构，使用可变长度路径 `*1..2` 确保覆盖底层子类。
6. 示例
    -用户问题：普通感冒属于什么大类？
   ' Cypher:
    MATCH (d:Disease {{name: '普通感冒'}})-[:SUB_CLASS_OF*1..3]->(ancestor)
    RETURN ancestor.name'

    用户问题：布洛芬禁忌什么？
    'Cypher:
    MATCH (d:Drug {{name: '布洛芬'}})-[:CONTRAINDICATED_WITH]->(c)
    RETURN c.name'

用户问题: {question}

请只输出 Cypher 查询语句，不要包含任何解释。"""

cypher_prompt = PromptTemplate(
    input_variables=["schema", "question"],
    template=CYPHER_GENERATION_TEMPLATE,
)

# 4. 创建 QA Chain（Schema 自动注入提示词）
chain = GraphCypherQAChain.from_llm(
    llm=llm,
    graph=graph,
    verbose=True,
    allow_dangerous_requests=True,   # ⚠️ 允许执行 Cypher 查询（仅限本地安全环境）
    return_intermediate_steps=True,  # 返回中间 Cypher 步骤
    cypher_prompt=cypher_prompt,     # 使用自定义提示词
)

# 5. 从命令行参数获取问题
if len(sys.argv) < 2:
    print("用法: python test_graphrag.py <你的问题>")
    print("示例: python test_graphrag.py 布洛芬能治什么病？有禁忌吗？")
    sys.exit(1)

query = " ".join(sys.argv[1:])
print("\n" + "=" * 60)
print(f"📝 问题: {query}")
print("=" * 60 + "\n")

result = chain.invoke({"query": query})

print("\n" + "=" * 60)
print("🤖 LLM 回答:")
print(result["result"])
print("=" * 60)

print("\n📊 生成的 Cypher 语句:")
for step in result.get("intermediate_steps", []):
    print(f"  → {step}")
