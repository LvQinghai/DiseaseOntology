"""智能问答服务（GraphRAG）."""

import os
from backend.repositories.neo4j_repository import Neo4jRepository
from backend.config import settings
from backend.models.query import QueryRequest, QueryResult

from langchain_community.graphs import Neo4jGraph
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate


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


class QueryService:
    """GraphRAG 智能问答服务"""

    def __init__(self, repo: Neo4jRepository):
        self._repo = repo

        # SSL 配置
        if not settings.ssl_verify:
            os.environ["SSL_CERT_FILE"] = ""
            os.environ["REQUESTS_CA_BUNDLE"] = ""

        # 初始化 LLM
        self._llm = ChatOpenAI(
            temperature=0,
            model=settings.llm_model,
            openai_api_key=settings.llm_api_key,
            openai_api_base=settings.llm_api_base,
        )

        # 初始化 LangChain Neo4jGraph（用于 Schema 提取）
        self._graph = Neo4jGraph(
            url=settings.neo4j_uri,
            username=settings.neo4j_user,
            password=settings.neo4j_password,
        )

        # 自定义 Cypher 生成提示词
        self._cypher_prompt = PromptTemplate(
            input_variables=["schema", "question"],
            template=CYPHER_GENERATION_TEMPLATE,
        )

        # 创建 GraphCypherQAChain
        self._chain = GraphCypherQAChain.from_llm(
            llm=self._llm,
            graph=self._graph,
            verbose=False,
            allow_dangerous_requests=True,
            return_intermediate_steps=True,
            cypher_prompt=self._cypher_prompt,
        )

    def ask(self, question: str) -> QueryResult:
        """执行 GraphRAG 问答."""
        try:
            result = self._chain.invoke({"query": question})

            cypher = None
            for step in result.get("intermediate_steps", []):
                cypher_val = None
                if isinstance(step, dict):
                    cypher_val = step.get("query", "")
                else:
                    cypher_val = str(step)
                if cypher_val:
                    cypher = cypher_val

            return QueryResult(
                answer=result.get("result", "无法获取答案"),
                cypher=cypher,
                raw_data=[],
            )
        except Exception as e:
            return QueryResult(
                answer=f"查询出错: {str(e)}",
                cypher=None,
                raw_data=[],
            )

    def get_schema_text(self) -> str:
        """获取 Schema 文本（供前端展示或调试）."""
        return self._graph.schema
