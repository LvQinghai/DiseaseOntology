"""智能问答服务（GraphRAG + 规则引擎降级）—— v3.0 prefix 隔离."""

import os
import re
from backend.repositories.neo4j_repository import Neo4jRepository
from backend.config import settings
from backend.models.query import QueryResult

from langchain_community.graphs import Neo4jGraph
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

# ---------------------------------------------------------------------------
# LLM Cypher 生成提示词（v3.0: 使用 {prefix} 占位符，运行时替换）
# ---------------------------------------------------------------------------

CYPHER_GENERATION_TEMPLATE = """任务：将用户问题转换为 Neo4j Cypher 查询语句。

图数据库 Schema:
{schema}

⚠️ 规则：
0. 数据库中所有数据均为中文。如果用户用英文提问，必须先把关键实体名翻译成中文后再写入 Cypher。
1. 节点标签和关系类型可能带有前缀（如 {prefix}Disease, {prefix}MANIFESTS_IN），请严格使用带前缀的名称。
2. 节点匹配使用 CONTAINS，例如 WHERE d.name CONTAINS '感冒'。
3. 关系方向必须严格匹配 Schema 中定义的方向。

用户问题: {question}

请只输出 Cypher 查询语句，不要包含任何解释。"""


# ---------------------------------------------------------------------------
# 规则引擎：意图识别 + 模板 Cypher 生成（v3.0: 使用 {prefix} 占位符）
# ---------------------------------------------------------------------------

_INTENT_PATTERNS: list[tuple[str, re.Pattern, str, str, str]] = [
    # --- 疾病症状 ---
    (
        "disease_symptoms",
        re.compile(r"(.+?)有什么症状|(.+?)有哪些症状|(.+?)什么症状|(.+?)的症状|(.+?)症状"),
        "MATCH (s:`{prefix}Symptom`)-[:`{prefix}MANIFESTS_IN`]->(d:`{prefix}Disease`) "
        "WHERE d.name CONTAINS $entity "
        "RETURN s.name AS result_name, labels(s)[0] AS result_type",
        "result_name",
        "{entity} 的症状包括：{results}",
    ),
    # --- 疾病的治疗/药物 ---
    (
        "disease_treatment",
        re.compile(r"(.+?)怎么治疗|(.+?)如何治疗|(.+?)怎样治疗"
                   r"|(.+?)用什么药|(.+?)吃什么药|(.+?)有哪些药"
                   r"|(.+?)的治疗"),
        "MATCH (d:`{prefix}Disease`)-[r]-(drug:`{prefix}Drug`) "
        "WHERE d.name CONTAINS $entity "
        "RETURN drug.name AS result_name, labels(drug)[0] AS result_type",
        "result_name",
        "{entity} 可用的治疗药物包括：{results}",
    ),
    # --- 药物治疗什么病 ---
    (
        "drug_treats",
        re.compile(r"(.+?)能治什么|(.+?)治疗什么|(.+?)可以治疗|"
                   r"(.+?)治什么|(.+?)主治什么|(.+?)用于治疗"),
        "MATCH (d:`{prefix}Drug`)-[r]-(disease:`{prefix}Disease`) "
        "WHERE d.name CONTAINS $entity "
        "RETURN disease.name AS result_name, labels(disease)[0] AS result_type",
        "result_name",
        "{entity} 可用于治疗：{results}",
    ),
    # --- 药物副作用 ---
    (
        "drug_side_effect",
        re.compile(r"(.+?)有什么副作用|(.+?)有哪些副作用|(.+?)什么副作用|"
                   r"(.+?)的副作用|(.+?)副作用"),
        "MATCH (d:`{prefix}Drug`)-[:`{prefix}HAS_SIDE_EFFECT`]->(se:`{prefix}SideEffect`) "
        "WHERE d.name CONTAINS $entity "
        "RETURN se.name AS result_name, labels(se)[0] AS result_type",
        "result_name",
        "{entity} 的副作用包括：{results}",
    ),
    # --- 疾病影响部位 ---
    (
        "disease_bodypart",
        re.compile(r"(.+?)影响什么部位|(.+?)影响哪些部位|(.+?)发生在什么部位|"
                   r"(.+?)在什么部位|(.+?)哪些部位|(.+?)的部位|(.+?)部位"),
        "MATCH (d:`{prefix}Disease`)-[:`{prefix}AFFECTS`]->(b:`{prefix}BodyPart`) "
        "WHERE d.name CONTAINS $entity "
        "RETURN b.name AS result_name, labels(b)[0] AS result_type",
        "result_name",
        "{entity} 影响的部位包括：{results}",
    ),
    # --- 部位相关疾病 ---
    (
        "bodypart_disease",
        re.compile(r"(.+?)有什么疾病|(.+?)有哪些疾病|(.+?)什么疾病|"
                   r"(.+?)的疾病|(.+?)会得什么病"),
        "MATCH (d:`{prefix}Disease`)-[:`{prefix}AFFECTS`]->(b:`{prefix}BodyPart`) "
        "WHERE b.name CONTAINS $entity "
        "RETURN d.name AS result_name, labels(d)[0] AS result_type",
        "result_name",
        "可能影响 {entity} 的疾病包括：{results}",
    ),
    # --- 症状相关疾病 ---
    (
        "symptom_disease",
        re.compile(r"(.+?)是什么病的症状|(.+?)是什么疾病的症状|"
                   r"(.+?)是什么的症状|(.+?)的症状|什么病会(.+)"),
        "MATCH (s:`{prefix}Symptom`)-[:`{prefix}MANIFESTS_IN`]->(d:`{prefix}Disease`) "
        "WHERE s.name CONTAINS $entity "
        "RETURN d.name AS result_name, labels(d)[0] AS result_type",
        "result_name",
        "可能出现 {entity} 症状的疾病包括：{results}",
    ),
    # --- 疾病分类 ---
    (
        "disease_category",
        re.compile(r"(.+?)属于什么大类|(.+?)是什么大类|(.+?)属于哪些大类|"
                   r"(.+?)属于哪一大类|(.+?)的大类|(.+?)的分类|(.+?)属于什么"),
        "MATCH (d:`{prefix}Disease`)-[:`{prefix}SUB_CLASS_OF`*1..3]->(ancestor:`{prefix}Disease`) "
        "WHERE d.name CONTAINS $entity "
        "RETURN ancestor.name AS result_name, labels(ancestor)[0] AS result_type",
        "result_name",
        "{entity} 属于以下大类：{results}",
    ),
    # --- 疾病的子类 ---
    (
        "disease_subclass",
        re.compile(r"(.+?)有哪些子类|(.+?)有什么子类|(.+?)哪些子类|"
                   r"(.+?)什么子类|(.+?)的子类|(.+?)子类"),
        "MATCH (child:`{prefix}Disease`)-[:`{prefix}SUB_CLASS_OF`]->(parent:`{prefix}Disease`) "
        "WHERE parent.name CONTAINS $entity "
        "RETURN child.name AS result_name, labels(child)[0] AS result_type",
        "result_name",
        "{entity} 的子类包括：{results}",
    ),
    # --- 药物禁忌 ---
    (
        "drug_contraindication",
        re.compile(r"(.+?)禁忌什么|(.+?)有什么禁忌|(.+?)禁忌|"
                   r"(.+?)不能和什么|(.+?)不能和"),
        "MATCH (d:`{prefix}Drug`)-[:`{prefix}CONTRAINDICATED_WITH`]->(c) "
        "WHERE d.name CONTAINS $entity "
        "RETURN c.name AS result_name, labels(c)[0] AS result_type",
        "result_name",
        "{entity} 的禁忌包括：{results}",
    ),
    # --- 药物可替代 ---
    (
        "drug_substitute",
        re.compile(r"(.+?)可以替代什么|(.+?)替代什么|(.+?)的替代品|"
                   r"(.+?)替代|(.+?)可以替代"),
        "MATCH (d:`{prefix}Drug`)-[:`{prefix}CAN_SUBSTITUTE`]->(sub:`{prefix}Drug`) "
        "WHERE d.name CONTAINS $entity "
        "RETURN sub.name AS result_name, labels(sub)[0] AS result_type",
        "result_name",
        "{entity} 可以替代的药物包括：{results}",
    ),
]


def _identify_intent(
    question: str,
) -> tuple[str, str, str, str, str] | None:
    """识别问题意图，返回 (意图名, 实体名, Cypher模板, 结果字段, 格式化模板)。"""
    q = question.strip()
    for intent_name, pattern, cypher, field, fmt_tpl in _INTENT_PATTERNS:
        m = pattern.search(q)
        if m:
            entity = ""
            for g_idx in range(1, m.lastindex + 1 if m.lastindex else 1):
                val = m.group(g_idx)
                if val and val.strip():
                    entity = val.strip()
                    break
            if entity and len(entity) >= 1:
                return (intent_name, entity, cypher, field, fmt_tpl)
    return None


def _format_results(entity: str, fmt_tpl: str, results: list[str]) -> str:
    """将结果列表格式化为自然语言."""
    if not results:
        return (
            f"已在知识图谱中找到「{entity}」，但暂无相关的关联数据。\n"
            f"可能是该实体尚未录入对应的关系（如症状、治疗药物等）。"
        )
    numbered = [f"{i+1}. {r}" for i, r in enumerate(results[:15])]
    more = f"\n... 以及其他共 {len(results)} 项" if len(results) > 15 else ""
    return fmt_tpl.format(entity=entity, results="\n".join(numbered)) + more + \
        "\n\n💡 提示：当前使用本地规则引擎回答（LLM API 不可用）。"


class QueryService:
    """GraphRAG + 规则引擎 智能问答服务（v3.0: prefix 隔离）"""

    def __init__(self, repo: Neo4jRepository):
        self._repo = repo

        if not settings.ssl_verify:
            os.environ["SSL_CERT_FILE"] = ""
            os.environ["REQUESTS_CA_BUNDLE"] = ""

        self._llm_available = False
        self._llm = None
        self._graph = None
        self._chain = None

        try:
            self._llm = ChatOpenAI(
                temperature=0,
                model=settings.llm_model,
                openai_api_key=settings.llm_api_key,
                openai_api_base=settings.llm_api_base,
            )
            self._graph = Neo4jGraph(
                url=settings.neo4j_uri,
                username=settings.neo4j_user,
                password=settings.neo4j_password,
            )
            self._cypher_prompt = PromptTemplate(
                input_variables=["schema", "prefix", "question"],
                template=CYPHER_GENERATION_TEMPLATE,
            )
            self._chain = GraphCypherQAChain.from_llm(
                llm=self._llm,
                graph=self._graph,
                verbose=False,
                allow_dangerous_requests=True,
                return_intermediate_steps=True,
                cypher_prompt=self._cypher_prompt,
            )
            self._llm_available = True
            print("✅ GraphRAG LLM 已就绪")
        except Exception as e:
            print(f"⚠️ LLM 初始化失败，将使用本地规则引擎: {e}")

    # ========================= 对外接口 =========================

    def ask(self, question: str, prefix: str = settings.DEFAULT_SYSTEM_PREFIX) -> QueryResult:
        """执行问答：先尝试 LLM，失败则降级到规则引擎。prefix 用于过滤当前系统数据。"""
        if self._llm_available and self._chain:
            llm_result = self._ask_llm(question, prefix)
            if llm_result is not None:
                return llm_result
        return self._ask_rules(question, prefix)

    def _ask_llm(self, question: str, prefix: str) -> QueryResult | None:
        """LLM GraphRAG 问答."""
        if not self._chain:
            return None
        try:
            result = self._chain.invoke({
                "query": question,
                "prefix": prefix,
            })

            cypher = None
            for step in result.get("intermediate_steps", []):
                cypher_val = None
                if isinstance(step, dict):
                    cypher_val = step.get("query", "")
                else:
                    cypher_val = str(step)
                if cypher_val:
                    cypher = cypher_val

            answer = result.get("result", "")
            _useless = [
                "出错", "错误", "quota", "抱歉", "不知道", "无法",
                "不确定", "不能确定", "I don't know", "no results",
                "没有找到", "未找到", "无法回答",
            ]
            if any(kw in answer for kw in _useless if kw):
                print(f"⚠️ LLM 返回无效答案，降级到规则引擎: {answer[:80]}")
                return None

            return QueryResult(
                answer=answer or "无法获取答案",
                cypher=cypher,
                raw_data=[],
            )
        except Exception as e:
            err_msg = str(e)
            if any(kw in err_msg.lower() for kw in
                   ["429", "quota", "insufficient", "timeout", "connection",
                    "ssl", "rate limit", "billing"]):
                print(f"⚠️ LLM 不可用，降级到规则引擎: {err_msg[:120]}")
                return None
            print(f"⚠️ LLM 异常，降级到规则引擎: {err_msg[:120]}")
            return None

    def _ask_rules(self, question: str, prefix: str) -> QueryResult:
        """规则引擎：意图识别 → 实体抽取 → 带前缀模板 Cypher 执行 → 格式化."""
        intent_info = _identify_intent(question)
        if not intent_info:
            return QueryResult(
                answer=(
                    "抱歉，我无法理解您的问题。\n\n"
                    "请尝试用以下方式提问：\n"
                    "  - 「感冒有什么症状？」\n"
                    "  - 「布洛芬能治什么病？」\n"
                    "  - 「糖尿病用什么药治疗？」\n"
                    "  - 「高血压属于什么大类？」\n"
                    "  - 「阿司匹林有什么副作用？」\n"
                    "  - 「消化系统疾病有哪些子类？」\n"
                    "  - 「青霉素的禁忌是什么？」\n\n"
                    "💡 提示：当前使用本地规则引擎回答（LLM API 不可用）。"
                ),
                cypher=None,
                raw_data=[],
            )

        _intent_name, entity, cypher_tpl, field_name, fmt_tpl = intent_info

        # 将 {prefix} 替换为实际的 prefix
        cypher = cypher_tpl.format(prefix=prefix)

        # 模糊搜索确认实体存在
        candidates = self._repo.search_nodes(entity, prefix)
        if not candidates:
            return QueryResult(
                answer=f"在知识图谱中未找到与「{entity}」相关的数据。\n\n"
                       f"请检查名称拼写，或尝试其他相关术语。",
                cypher=cypher.replace("$entity", f"'{entity}'"),
                raw_data=[],
            )

        best_entity = candidates[0].get("name", entity)

        # 执行带前缀的 Cypher
        try:
            records = self._repo.execute_cypher(
                cypher.replace("$entity", f"'{best_entity}'")
            )
        except Exception as e:
            return QueryResult(
                answer=f"查询执行失败: {str(e)[:200]}",
                cypher=cypher.replace("$entity", f"'{best_entity}'"),
                raw_data=[],
            )

        result_names = [r.get(field_name, "") for r in records if r.get(field_name)]
        answer = _format_results(best_entity, fmt_tpl, result_names)

        return QueryResult(
            answer=answer,
            cypher=cypher.replace("$entity", f"'{best_entity}'"),
            raw_data=[dict(r) for r in records],
        )

    def get_schema_text(self) -> str:
        """获取 Schema 文本."""
        if self._graph:
            return self._graph.schema
        return "LLM 不可用，Schema 无法生成。规则引擎模式已激活。"
