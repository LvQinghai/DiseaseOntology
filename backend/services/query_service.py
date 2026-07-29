"""v3.7: GraphRAG 智能问答服务。

基于 GraphRAG 系统架构（6层管道）：
  意图识别 → 实体链接 → Schema+语义检索 → Cypher生成 → 校验修复 → 执行+答案合成
降级路径：动态规则引擎（模板化自然语言输出）。

参考文档：docs/v3.5-design.md / GraphRAG 系统架构设计
"""

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend.config import settings
from backend.repositories.neo4j_repository import Neo4jRepository

# 引入 SystemService 类型提示（避免循环导入）
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from backend.services.system_service import SystemService

logger = logging.getLogger(__name__)

# 通用分类词：作为实体名命中时优先级最低（避免"疾病"盖住"发热"）
_GENERIC_ENTITY_TERMS = {
    "疾病", "药物", "药品", "症状", "副作用",
    "身体部位", "部位", "分类", "疾病分类",
}


class QueryService:
    """图谱知识查询服务 —— 语义驱动，多系统通用。"""

    def __init__(
        self,
        repo: Neo4jRepository,
        system_svc: "SystemService | None" = None,
    ):
        self._repo = repo
        self._system_svc = system_svc
        self._http = requests.Session()
        retry = Retry(total=2, backoff_factor=0.5,
                      status_forcelist=[429, 500, 502, 503, 504])
        self._http.mount("https://", HTTPAdapter(max_retries=retry))
        self._http.mount("http://", HTTPAdapter(max_retries=retry))

        # 三层缓存（prefix → (timestamp, data)）
        self._schema_cache: dict[str, tuple[float, object]] = {}    # L2, TTL 30min
        self._semantics_cache: dict[str, tuple[float, object]] = {} # L3, TTL 30min
        self._result_cache: dict[str, tuple[float, dict]] = {}      # L1, TTL 5min
        self._cache_ttl = 1800          # 30 min（L2/L3）
        self._result_cache_ttl = 300    # 5 min（L1）

        # Few-shot 示例库（启动时加载）
        self._fewshots: list[dict] = self._load_fewshots()

    def _cache_get(self, cache: dict, key: str, ttl: float | None = None):
        entry = cache.get(key)
        if entry and time.time() - entry[0] < (ttl if ttl is not None else self._cache_ttl):
            return entry[1]
        return None

    def _cache_set(self, cache: dict, key: str, value):
        cache[key] = (time.time(), value)

    # ── 缓存主动失效（v3.8）────────────────────────

    def invalidate_semantics_cache(self, prefix: str):
        """语义配置变更后调用：清除该系统的语义缓存 + 结果缓存。"""
        self._semantics_cache.pop(prefix, None)
        self._clear_result_cache_for_prefix(prefix)

    def invalidate_schema_cache(self, prefix: str):
        """图谱数据导入后调用：清除 Schema 缓存 + 结果缓存。"""
        self._schema_cache.pop(prefix, None)
        self._clear_result_cache_for_prefix(prefix)

    def _clear_result_cache_for_prefix(self, prefix: str):
        keys = [k for k in self._result_cache if k.startswith(f"{prefix}:")]
        for k in keys:
            self._result_cache.pop(k, None)

    # ── L1 查询结果缓存 ─────────────────────────

    def _get_cached_result(self, question: str, prefix: str) -> dict | None:
        key = f"{prefix}:{question.strip().lower()}"
        return self._cache_get(self._result_cache, key, ttl=self._result_cache_ttl)

    def _set_cached_result(self, question: str, prefix: str, result: dict):
        key = f"{prefix}:{question.strip().lower()}"
        self._cache_set(self._result_cache, key, result)

    # ── Few-shot 示例库 ─────────────────────────

    def _load_fewshots(self) -> list[dict]:
        """从 backend/data/fewshots.jsonl 加载 Few-shot 示例。"""
        path = Path(__file__).parent.parent / "data" / "fewshots.jsonl"
        if not path.exists():
            return []
        shots = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        shots.append(json.loads(line))
            logger.info(f"已加载 {len(shots)} 条 Few-shot 示例")
        except Exception as e:
            logger.warning(f"Few-shot 示例加载失败: {e}")
        return shots

    def _get_relevant_fewshots(self, question: str, prefix: str, top_k: int | None = None) -> list[dict]:
        """按字符重叠度检索与问题最相关的 Few-shot 示例。"""
        if top_k is None:
            top_k = settings.fewshot_top_k
        candidates = [s for s in self._fewshots if s.get("prefix") == prefix]
        if not candidates:
            return []
        q_chars = set(question)
        scored = []
        for s in candidates:
            overlap = len(q_chars & set(s.get("question", "")))
            if overlap > 0:
                scored.append((overlap, s))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:top_k]]

    # ═══════════════════════════════════════════
    # 公共入口
    # ═══════════════════════════════════════════

    def ask(self, question: str, prefix: str = "MED_") -> dict:
        """回答用户的图谱知识查询。

        优先查 L1 结果缓存 → LLM 6层管道 → 失败降级到动态规则引擎。
        降级时若规则引擎有结果，在答案前标注来源提示。
        """
        # L1 结果缓存检查（v3.8）
        cached = self._get_cached_result(question, prefix)
        if cached is not None:
            logger.info(f"L1 缓存命中: {question[:30]}")
            return cached

        llm_attempted = _llm_configured()
        try:
            llm_result = self._ask_llm(question, prefix)
            if llm_result and llm_result.get("answer"):
                self._set_cached_result(question, prefix, llm_result)
                return llm_result
        except Exception as e:
            logger.warning(f"LLM 查询失败，降级到规则引擎: {e}")

        rule_result = self._ask_rules(question, prefix)

        # LLM 路径失败但规则引擎找到数据时，标注结果来源（v3.8）
        if (
            llm_attempted
            and rule_result
            and rule_result.get("raw_data")
            and rule_result.get("answer")
        ):
            rule_result["answer"] = (
                "💡 通过 AI 语义未能匹配到答案，但通过规则匹配到以下疑似信息，供参考：\n\n"
                + rule_result["answer"]
            )

        # 规则引擎结果也缓存（避免重复问题的规则路径开销）
        if rule_result and rule_result.get("answer"):
            self._set_cached_result(question, prefix, rule_result)
        return rule_result

    # ═══════════════════════════════════════════
    # LLM 路径
    # ═══════════════════════════════════════════

    def _ask_llm(self, question: str, prefix: str) -> dict | None:
        """GraphRAG 主流程（6层管道）：
        意图识别 → 实体链接 → Schema+语义检索 → Cypher生成 → 校验修复 → 执行+答案合成。
        """
        if not _llm_configured():
            return None

        # 1. 意图识别 + 实体抽取（一次 LLM 调用）
        intent_data = self._extract_intent_and_entities(question, prefix)
        if not intent_data:
            logger.info(f"[failure_stage=intent_extraction] {question[:30]}")
            return None
        intent = intent_data.get("intent", "unknown")
        question_type = intent_data.get("question_type", "")

        # 2. 实体链接：将自然语言实体名 → 图谱节点名，并提取命中的标签
        linked, linked_labels = self._link_entities(intent_data.get("entities", []), prefix)

        # 3. Schema + 语义上下文检索（并行执行，v3.8）
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_schema = pool.submit(self._get_schema_summary, prefix, linked_labels)
            f_sem = pool.submit(self._build_semantics_section, prefix)
            schema_context = f_schema.result()
            semantics_section = f_sem.result()

        # 4~5. Cypher 生成 + 校验修复（最多 2 次修复）
        cypher, error_msg = None, ""
        for attempt in range(3):
            if attempt == 0:
                cypher = self._generate_cypher(
                    question, intent, question_type, linked,
                    schema_context, semantics_section, prefix
                )
            else:
                if cypher is None:
                    logger.info(f"[failure_stage=cypher_generation] {question[:30]}")
                    return None
                cypher = self._repair_cypher(
                    question, cypher, error_msg, schema_context, semantics_section, prefix
                )

            if not cypher or "CANNOT_GENERATE" in cypher.upper():
                logger.info(f"[failure_stage=cypher_generation] {question[:30]}")
                return None

            # 清洗 LLM 输出：剥离 markdown 代码块和解释性文字
            cypher = self._clean_cypher(cypher)
            if not cypher:
                logger.info(f"[failure_stage=cypher_generation] 清洗后为空: {question[:30]}")
                return None

            is_valid, error_msg = self._validate_cypher(cypher)
            if is_valid:
                break
            logger.info(f"Cypher 校验失败（第{attempt + 1}次）: {error_msg[:150]} | 原文: {cypher[:150]}")
        else:
            logger.warning(f"[failure_stage=validation] Cypher 全部 3 次尝试均失败（问题: {question[:30]}）")
            return None

        # 6. 执行 + LLM 答案合成（意图感知，v3.8）
        try:
            data = self._repo._run(cypher)
        except Exception as e:
            logger.warning(f"[failure_stage=execution] Cypher 执行失败: {e}")
            return None

        # 查询结果为空：视为 LLM 未找到有用答案，降级规则引擎兜底
        # （常见于 Cypher 方向猜错/实体匹配偏差，规则引擎可能仍能找到数据）
        if not data:
            logger.info(
                f"[failure_stage=no_results] 查询成功但 0 条数据: {question[:30]} "
                f"| Cypher: {cypher[:120]}"
            )
            return None

        answer = self._synthesize_answer(question, data, prefix, intent)

        # Prompt 大小监控（估算：1 token ≈ 4 字符）
        prompt_chars = len(schema_context) + len(semantics_section) + len(linked) + len(question)
        est_tokens = prompt_chars // 4
        if est_tokens > settings.prompt_token_warn:
            logger.warning(
                f"Prompt 较大: ~{est_tokens} tokens "
                f"(schema={len(schema_context)}ch, semantics={len(semantics_section)}ch, "
                f"问题={len(question)}ch)"
            )

        return {"answer": answer, "cypher": cypher, "raw_data": data}

    # ── GraphRAG 子步骤 ──────────────────────────

    def _extract_intent_and_entities(self, question: str, prefix: str) -> dict | None:
        """第1层：意图识别 + 实体抽取（一次 LLM 调用）。"""
        prompt = f"""分析以下用户问题，提取查询意图和关键实体名称。

## 查询意图分类
- lookup: 实体查找（"XXX是什么""XXX和什么有关"）
- aggregate: 聚合统计（"多少个""有多少"）
- path: 路径分析（"XXX和YYY什么关系""如何关联"）
- compare: 对比（"区别""不同""对比"）
- unknown: 其他

## 图谱说明
所有节点和关系类型都以 "{prefix}" 开头。
节点属性包含 name 字段。

## 用户问题
{question}

## 输出格式
只输出 JSON，不要额外文字：
{{
  "intent": "lookup",
  "entities": ["实体1", "实体2"],
  "question_type": "用户具体想问什么，一句话概括"
}}"""
        resp = self._call_llm(prompt)
        if not resp:
            return None
        return self._parse_json_response(resp)

    def _link_entities(self, entities: list[str], prefix: str) -> tuple[str, list[str]]:
        """第2层：实体链接，将自然语言实体名映射到图谱节点。

        Returns:
            (格式化的链接文本, 匹配到的标签列表) — 用于 Schema 相关性过滤
        """
        if not entities:
            return "（未提取到实体）", []

        linked = []
        matched_labels: set[str] = set()
        for ent in entities:
            rows = self._repo._run(
                "MATCH (n) WHERE any(l IN labels(n) WHERE l STARTS WITH $prefix) "
                "AND n.name CONTAINS $name "
                "RETURN n.name AS name, labels(n) AS labels LIMIT 5",
                prefix=prefix,
                name=ent,
            )
            if rows:
                names = [r["name"] for r in rows]
                # 提取匹配到的标签（去掉前缀用于过滤 Schema）
                for r in rows:
                    for lbl in r.get("labels", []):
                        if lbl.startswith(prefix):
                            matched_labels.add(lbl)
                linked.append(f"{ent} → 匹配到: {', '.join(names)}")
            else:
                linked.append(f"{ent} → 图谱中未找到匹配")

        return "\n".join(linked), list(matched_labels)

    def _generate_cypher(
        self, question: str, intent: str, question_type: str,
        linked_entities: str,
        schema_context: str, semantics_section: str, prefix: str
    ) -> str | None:
        """第4层：LLM 生成 Cypher，结合意图上下文生成更精准的查询。"""
        intent_hint = {
            "lookup": "这是一个实体查找查询，需要找出指定实体关联的所有信息",
            "aggregate": "这是一个聚合统计查询，需要用 count/collect 统计数量",
            "path": "这是一个路径分析查询，需要找出两个实体之间的关联路径",
            "compare": "这是一个对比查询，需要比较两个实体的差异",
            "unknown": "",
        }.get(intent, "")

        # Few-shot 示例注入（v3.8）：检索最相关的 1~2 个示例
        fewshots = self._get_relevant_fewshots(question, prefix)
        fewshot_section = ""
        if fewshots:
            examples = "\n\n".join(
                f"问题：{s['question']}\nCypher：{s['cypher']}" for s in fewshots
            )
            fewshot_section = f"## 参考示例\n{examples}\n\n"

        prompt = f"""你是一个 Cypher 查询专家。根据以下信息生成一条可执行的 Cypher 查询。

## 查询意图
{intent_hint}
用户问题类型: {question_type}

## 图谱 Schema
{schema_context}

## 关系语义说明
{semantics_section}

{fewshot_section}## 匹配到的实体
{linked_entities}

## 重要规则
1. 所有标签和关系类型必须以 "{prefix}" 开头
2. **关系方向必须严格遵循 Schema 中的「关系模式」，禁止凭常识反转方向**
3. 只返回纯 Cypher 语句，不要用 ``` 代码块包裹，不要附加任何解释
4. 如果问题无法用图谱数据回答，直接输出 "CANNOT_GENERATE"
5. 使用 CONTAINS 进行模糊匹配字符串
6. 查询结果中返回有意义的字段（如 name、rel_type 等），不要只返回计数
7. 用 RETURN DISTINCT 避免重复
8. **分类遍历**：若问题中的实体是分类节点（如"心血管疾病""消化系统疾病"），
   而具体数据通常挂在它的子类上，需要沿 SUB_CLASS_OF 向下遍历：
   `MATCH (x)-[r]->(sub)-[:{prefix}SUB_CLASS_OF]->(cat) WHERE cat.name CONTAINS '分类名'`
   而不是直接匹配分类节点本身

## 用户问题
{question}"""
        return self._call_llm(prompt)

    def _validate_cypher(self, cypher: str) -> tuple[bool, str]:
        """第5层：用 EXPLAIN 校验 Cypher 语法，返回 (是否通过, 错误信息)。"""
        # 安全检查：禁止写操作
        upper = cypher.upper().strip()
        for kw in ("CREATE ", "MERGE ", "DELETE ", "SET ", "REMOVE "):
            if upper.startswith(kw) or f" {kw}" in upper:
                return False, f"禁止写操作: {kw.strip()}"

        try:
            self._repo._run(f"EXPLAIN {cypher}")
            return True, ""
        except Exception as e:
            return False, str(e)

    def _clean_cypher(self, text: str) -> str:
        """从 LLM 响应中提取纯 Cypher。

        推理模型常无视"不要代码块包裹"的指令，返回
        ```cypher ... ``` 或"分析如下：\nMATCH ..."等带解释的文本，
        直接送 EXPLAIN 校验必挂，需先清洗。
        """
        if not text:
            return ""
        # 1. 提取 markdown 代码块内容
        m = re.search(r'```(?:cypher|sql)?\s*\n?(.*?)```', text, re.DOTALL | re.IGNORECASE)
        if m:
            text = m.group(1)
        # 2. 从第一个 Cypher 关键字行开始，丢弃前面的解释性文字
        keywords = ("MATCH", "OPTIONAL", "WITH", "UNWIND", "RETURN", "CALL", "EXPLAIN")
        lines = text.strip().splitlines()
        for i, line in enumerate(lines):
            if line.strip().upper().startswith(keywords):
                return "\n".join(lines[i:]).strip().rstrip(";")
        return ""

    def _repair_cypher(
        self, question: str, bad_cypher: str, error: str,
        schema_context: str, semantics_section: str, prefix: str
    ) -> str | None:
        """第5层修复：将错误信息回灌 LLM，重新生成。"""
        prompt = f"""你之前生成的 Cypher 查询执行出错，请修正。

## 原始 Cypher
{bad_cypher}

## 错误信息
{error}

## 相关 Schema
{schema_context}

## 关系语义
{semantics_section}

## 用户问题
{question}

## 要求
1. 标签和关系类型必须以 "{prefix}" 开头
2. 只输出修正后的 Cypher，不要附加解释
3. 确保语法正确"""
        return self._call_llm(prompt)

    def _synthesize_answer(self, question: str, data: list[dict], prefix: str, intent: str = "unknown") -> str:
        """第6层：LLM 将查询结果合成自然语言回答（意图感知，v3.8）。"""
        if not data:
            return "未找到相关数据。"

        # 结果裁剪：最多展示配置的行数
        max_rows = settings.answer_max_rows
        trimmed = data[:max_rows]
        note = f"\n（共 {len(data)} 条结果，仅展示前 {max_rows} 条）" if len(data) > max_rows else ""

        data_json = json.dumps(trimmed, ensure_ascii=False, indent=2)[:settings.prompt_result_max_chars]

        # 意图感知的回答风格（v3.8）
        style_hint = {
            "lookup": "逐条列出所有关联关系。",
            "aggregate": "先给出统计数字，再简要列举（如有）。",
            "path": "按顺序描述实体之间的关联路径。",
            "compare": "分别说明，再指出差异点。",
            "unknown": "",
        }.get(intent, "")

        prompt = f"""你是一个严格的图谱结果转述器。你的任务是将 JSON 结果中的内容重新组织成自然语言，**不得添加任何图谱结果中没有的信息**。

用户问题: {question}
查询结果（JSON）: {data_json}

## 回答风格
{style_hint}

## 硬性规则（必须遵守）
1. **严格忠实于数据**：只能复述 JSON 中出现的关系，一个字都不能多。例如数据只有"急性胃肠炎→[影响]→肠道"，就只说"急性胃肠炎影响肠道"，不要加"可能引起不适"等任何额外解释。
2. **简洁**：每个关系用一句话说完，不超过 3 句话。
3. 如果数据中 A→B 的关系用"影响"表示，说"甲影响乙"。
4. 如果有多条结果，分点列出。
5. **禁止**：禁止使用你的医学/领域知识来补充说明、推断因果、解释含义。只做"数据转文字"的工作。"""
        answer = self._call_llm(prompt)
        if answer:
            return answer + note
        # LLM 失败时降级到模板化输出
        return self._format_cypher_result(data, question, prefix) + note

    def _parse_json_response(self, text: str) -> dict | None:
        """尝试从 LLM 响应中解析 JSON（处理 ```json 包裹 / 多余文字 / 嵌套括号）。"""
        # 1. 优先尝试提取 ```json ... ``` 代码块中的完整 JSON
        m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if m:
            candidate = m.group(1)
            # 找到最后一个匹配的 }，处理嵌套情况
            last_brace = candidate.rfind("}")
            if last_brace != -1:
                candidate = candidate[:last_brace + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        # 2. 直接尝试解析整个文本（适用于 LLM 输出就是纯 JSON 的情况）
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # 3. 兜底：用括号计数找到第一个完整的 JSON 对象
        idx = text.find("{")
        if idx == -1:
            logger.warning(f"JSON 解析失败（未找到 JSON）: {text[:200]}")
            return None
        depth = 0
        in_string = False
        escape = False
        for i in range(idx, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[idx:i + 1])
                    except json.JSONDecodeError:
                        break

        logger.warning(f"JSON 解析失败: {text[:200]}")
        return None

    # ═══════════════════════════════════════════
    # 动态规则引擎路径
    # ═══════════════════════════════════════════

    def _ask_rules(self, question: str, prefix: str) -> dict:
        """动态规则引擎：基于系统语义 + Schema 做通用匹配，生成自然语言回答。"""
        semantics = self._get_semantics(prefix)

        # 1. 尝试匹配用户问题中的关键实体名称
        node = self._find_node_by_question(question, prefix)
        if not node:
            return {
                "answer": self._build_fallback_response(question, prefix, semantics),
                "raw_data": [],
            }

        entity_name = node.get("name", "")

        # 2. 查询该实体的所有关联关系（包括方向）
        results = self._repo._run(
            "MATCH (n)-[r]-(m) "
            "WHERE n.name = $name AND any(label IN labels(n) WHERE label STARTS WITH $prefix) "
            "AND any(label IN labels(m) WHERE label STARTS WITH $prefix) "
            "RETURN n.name AS source, type(r) AS rel_type, labels(n) AS source_labels, "
            "labels(m) AS target_labels, m.name AS target, "
            "startNode(r).name = n.name AS is_outgoing "
            "LIMIT 30",
            name=entity_name,
            prefix=prefix,
        )

        if not results:
            return {
                "answer": f"在知识图谱中找到了「{entity_name}」，但它暂时没有关联其他实体。",
                "raw_data": [],
            }

        # 3. 按关系类型和方向分组
        # 注意：Cypher 中 source 别名恒为查询实体本身（n.name），
        # target 别名才是关系另一端（m.name），两个方向都应取 target
        out_rels: dict[str, list[str]] = {}  # entity → rel → ...
        in_rels: dict[str, list[str]] = {}   # ... → rel → entity
        for row in results:
            rel_type = row.get("rel_type", "")
            if row.get("is_outgoing"):
                out_rels.setdefault(rel_type, []).append(row.get("target", ""))
            else:
                in_rels.setdefault(rel_type, []).append(row.get("target", ""))

        # 4. 理解问题意图：判断用户关注的方向
        question_lower = question.lower()
        intent_out = any(w in question_lower for w in ["影响", "导致", "引起", "产生", "造成", "引发"])

        unconfigured: set[str] = set()
        lines: list[str] = []

        # 5. 生成自然语言回答
        if intent_out and out_rels:
            lines = self._format_rel_groups(entity_name, out_rels, semantics, unconfigured, outgoing=True)
            if in_rels:
                lines.append("")
                lines.extend(self._format_rel_groups(entity_name, in_rels, semantics, unconfigured, outgoing=False))
        elif intent_out and in_rels:
            # 用户问"X影响什么"但数据中X只被其他实体影响
            lines = self._format_rel_groups(entity_name, in_rels, semantics, unconfigured, outgoing=False)
            if out_rels:
                lines.append("")
                lines.extend(self._format_rel_groups(entity_name, out_rels, semantics, unconfigured, outgoing=True))
        else:
            lines = self._format_rel_groups(entity_name, out_rels, semantics, unconfigured, outgoing=True)
            if in_rels:
                if lines:
                    lines.append("")
                lines.extend(self._format_rel_groups(entity_name, in_rels, semantics, unconfigured, outgoing=False))

        answer = "\n".join(lines) if lines else f"「{entity_name}」在知识图谱中有 {len(results)} 条关联。"
        answer += f"\n\n（共 {len(results)} 条关联）"

        # 只在存在未配置语义的关系类型时才提示
        if unconfigured:
            unconfigured_list = "、".join(sorted(unconfigured))
            answer += f"\n💡 关系类型「{unconfigured_list}」尚未配置语义说明，可在「对关系进行语义说明」中完善，使回答更加自然。"

        return {"answer": answer, "raw_data": results}

    def _format_rel_groups(self, entity_name: str, rel_groups: dict, semantics, unconfigured: set,
                           outgoing: bool) -> list[str]:
        """将关系分组格式化为自然语言句子。
        根据语义配置的显示名称生成「A 影响 B」这样的自然语句。
        """
        lines: list[str] = []
        for rel_type, entities in rel_groups.items():
            sem = self._find_semantic(semantics, rel_type)
            is_configured = sem.display_name != rel_type
            display = sem.display_name if is_configured else f"「{rel_type}」"

            if not is_configured:
                unconfigured.add(rel_type)

            if len(entities) == 1:
                other = entities[0]
            else:
                other = "、".join(entities)

            if outgoing:
                lines.append(f"{entity_name}{display}{other}")
            else:
                lines.append(f"{other}{display}{entity_name}")
        return lines

    # ═══════════════════════════════════════════
    # 辅助方法
    # ═══════════════════════════════════════════

    def _get_semantics(self, prefix: str):
        """获取系统的语义配置（带缓存，TTL 30min）。"""
        cached = self._cache_get(self._semantics_cache, prefix)
        if cached is not None:
            return cached
        if self._system_svc:
            result = self._system_svc.get_semantics_for_query(prefix)
            self._cache_set(self._semantics_cache, prefix, result)
            return result
        return None

    def _build_semantics_section(self, prefix: str) -> str:
        """构建 LLM prompt 中的关系语义说明段落。

        包含用户配置的 显示名/描述/方向(源→目标)/基数/对称性/传递性，
        其中 源实体→目标实体 的方向提示对 Cypher 生成至关重要。
        """
        sem = self._get_semantics(prefix)
        if not sem or not sem.semantics:
            return "(尚未配置关系语义说明，请根据关系类型名称推断含义)"

        lines = ["| 关系类型 | 显示名 | 语义描述 | 方向(源→目标) | 基数 | 对称性 | 传递性 |"]
        lines.append("|---|---|---|---|---|---|---|")
        for s in sem.semantics:
            direction = "-"
            if s.source_hint or s.target_hint:
                direction = f"{s.source_hint or '?'} → {s.target_hint or '?'}"
            lines.append(
                f"| {s.rel_type} | {s.display_name or '-'} | "
                f"{s.description or '-'} | {direction} | {s.cardinality or '-'} | "
                f"{s.symmetry or '-'} | {s.transitivity or '-'} |"
            )
        return "\n".join(lines)

    def _get_system_description(self, prefix: str) -> str:
        sem = self._get_semantics(prefix)
        if sem and sem.domain_description:
            return sem.domain_description
        return f"知识图谱（前缀: {prefix}）"

    def _get_schema_raw(self, prefix: str) -> tuple[list, list, list] | None:
        """获取 Schema 原始数据（标签+关系+关系模式），带缓存。"""
        cached = self._cache_get(self._schema_cache, prefix)
        if cached is not None:
            return cached

        try:
            labels_result = self._repo._run(
                "MATCH (n) WHERE any(label IN labels(n) WHERE label STARTS WITH $prefix) "
                "UNWIND labels(n) AS lbl "
                "WITH lbl, count(n) AS cnt "
                "WHERE lbl STARTS WITH $prefix "
                "RETURN lbl, cnt ORDER BY lbl",
                prefix=prefix,
            )
            rel_result = self._repo._run(
                "MATCH ()-[r]->() WHERE type(r) STARTS WITH $prefix "
                "RETURN DISTINCT type(r) AS rel_type ORDER BY rel_type",
                prefix=prefix,
            )
            # 关系模式（实际数据方向）：LLM 必须看到 (:源)-[:关系]->(:目标)
            # 才能生成方向正确的 Cypher，否则只能凭常识猜（极易猜反）
            patterns_result = self._repo._run(
                "MATCH (a)-[r]->(b) WHERE type(r) STARTS WITH $prefix "
                "WITH [l IN labels(a) WHERE l STARTS WITH $prefix][0] AS src, "
                "type(r) AS rel, [l IN labels(b) WHERE l STARTS WITH $prefix][0] AS tgt "
                "RETURN DISTINCT src, rel, tgt ORDER BY rel",
                prefix=prefix,
            )
            data = (labels_result, rel_result, patterns_result)
            self._cache_set(self._schema_cache, prefix, data)
            return data
        except Exception:
            return None

    def _get_schema_summary(self, prefix: str, linked_labels: list[str] | None = None) -> str:
        """获取图谱 Schema 摘要（用于 LLM prompt）。

        Args:
            prefix: 系统前缀
            linked_labels: 可选。实体链接命中的标签列表，只显示相关标签，缩小 Schema 上下文。
        """
        raw = self._get_schema_raw(prefix)
        if raw is None:
            return "(无法获取 Schema 摘要)"

        labels_result, rel_result, patterns_result = raw

        # 双重过滤（v3.8）：标签过滤 + 关系类型过滤
        if linked_labels:
            # 标签过滤：只保留 linked_labels 中出现的标签
            filtered = [r for r in labels_result if r["lbl"] in linked_labels]
            if filtered:
                labels_result = filtered
                # 关系模式过滤：只保留涉及命中标签的模式（方向信息）
                label_set = set(linked_labels)
                patterns_result = [
                    p for p in patterns_result
                    if p.get("src") in label_set or p.get("tgt") in label_set
                ] or patterns_result
                rel_result = [
                    {"rel_type": rel}
                    for rel in sorted({p["rel"] for p in patterns_result})
                ]

        label_lines = [f"- {r['lbl']} ({r['cnt']} 个节点)" for r in labels_result]
        rel_lines = [f"- {r['rel_type']}" for r in rel_result]
        pattern_lines = [f"- (:{p['src']})-[:{p['rel']}]->(:{p['tgt']})" for p in patterns_result]

        return (
            f"节点标签 ({len(labels_result)}):\n"
            + "\n".join(label_lines)
            + f"\n\n关系模式（实际数据方向，生成 Cypher 时必须严格遵守） ({len(patterns_result)}):\n"
            + "\n".join(pattern_lines)
            + f"\n\n关系类型 ({len(rel_result)}):\n"
            + "\n".join(rel_lines)
        )

    def _find_node_by_question(self, question: str, prefix: str) -> dict | None:
        """从问题中尝试匹配知识图谱中的实体。

        匹配规则：最长名称优先；等长时优先非通用分类词
        （避免"什么疾病有发热的症状"匹配到"疾病"而非"发热"）。
        """
        # 获取所有节点名称
        try:
            nodes = self._repo._run(
                "MATCH (n) WHERE any(label IN labels(n) WHERE label STARTS WITH $prefix) "
                "RETURN n.name AS name, labels(n) AS labels",
                prefix=prefix,
            )
        except Exception:
            return None

        # 模糊匹配：问题中包含实体名称
        best = None
        best_len = 0
        best_generic = True
        for node in nodes:
            name = node.get("name", "")
            if name and len(name) >= 2 and name in question:
                generic = name in _GENERIC_ENTITY_TERMS
                if len(name) > best_len or (
                    len(name) == best_len and best_generic and not generic
                ):
                    best = {"name": name, "labels": node.get("labels", [])}
                    best_len = len(name)
                    best_generic = generic

        return best

    @dataclass
    class _EmptySemantic:
        display_name: str = ""
        description: str = ""
        cardinality: str = ""
        symmetry: str = ""
        transitivity: str = ""

    def _find_semantic(self, semantics, rel_type: str):
        """在语义列表中查找指定关系类型。

        SQLite 未配置时回退到预置语义（v3.8），避免"未配置语义"提示
        出现在已有预置映射的关系类型上（如 MED_SUB_CLASS_OF）。
        """
        if semantics:
            for s in semantics.semantics:
                if s.rel_type == rel_type:
                    return s
        preset = _PRESET_SEMANTICS.get(rel_type)
        if preset:
            return self._EmptySemantic(
                display_name=preset["display_name"],
                description=preset.get("description", ""),
                cardinality=preset.get("cardinality", ""),
                symmetry=preset.get("symmetry", ""),
                transitivity=preset.get("transitivity", ""),
            )
        return self._EmptySemantic(display_name=rel_type)

    def _format_cypher_result(
        self, data: list[dict], question: str, prefix: str
    ) -> str:
        """将 Cypher 查询结果格式化为自然语言回答。"""
        if not data:
            return "查询未返回结果，图谱中可能没有相关信息。"

        if len(data) == 1 and len(data[0]) == 1:
            val = list(data[0].values())[0]
            return str(val)

        if all(len(row) == 2 for row in data):
            keys = list(data[0].keys())
            if keys == ["name", "count"]:
                semantics = self._get_semantics(prefix)
                lines = ["查询结果："]
                for row in data:
                    sem = self._find_semantic(semantics, row.get("rel_type", ""))
                    label: str = sem.display_name or ""
                    lines.append(f"  • {label}: {row[keys[1]]} 条")
                return "\n".join(lines)

        lines = ["查询结果："]
        for row in data[:15]:
            pairs = []
            for k, v in row.items():
                val = str(v)[:60]
                pairs.append(f"{k}: {val}")
            lines.append("  • " + " | ".join(pairs))
        if len(data) > 15:
            lines.append(f"  ... (共 {len(data)} 条，仅展示前 15 条)")

        return "\n".join(lines)

    def _build_fallback_response(
        self, question: str, prefix: str, semantics
    ) -> str:
        """构建降级提示回答。"""
        lines = [
            "未能直接匹配您的问题。您可以尝试：",
            "",
            "1. 输入图谱中具体存在的实体或关系名称",
        ]

        # 从语义中提取示例问题
        if semantics and semantics.semantics:
            types = list({s.rel_type for s in semantics.semantics})[:5]
            lines.append(
                f"2. 该图谱包含以下关系类型: {', '.join(types)}"
            )
            # 为 LLM 路径提供提示
            if _llm_configured():
                lines.append("3. 更复杂的查询将交由 AI 理解（LLM 模式已启用）")

        lines.append(
            f"\n💡 提示: 点击「对关系进行语义说明」完善当前系统的关系语义描述，可以显著提升查询准确率。"
        )
        return "\n".join(lines)

    def _call_llm(self, prompt: str) -> str | None:
        """调用 LLM API。"""
        try:
            # 注意：不能用 urljoin(base, "/chat/completions")，
            # 第二个参数以 / 开头会丢弃 base 中的 /v1 路径
            url = settings.llm_api_base.rstrip('/') + '/chat/completions'
            resp = self._http.post(
                url,
                json={
                    "model": settings.llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": settings.llm_max_tokens,
                },
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                timeout=settings.llm_timeout,
                verify=settings.ssl_verify,
            )
            if resp.status_code == 429:
                logger.warning(
                    "LLM API 配额不足或触发限流 (429 insufficient_quota)，"
                    "请检查网关账户额度/套餐，恢复前查询将降级到规则引擎"
                )
                return None
            if resp.status_code != 200:
                logger.warning(f"LLM API 返回 {resp.status_code}: {resp.text[:200]}")
                return None

            body = resp.json()
            choices = body.get("choices", [])
            if not choices:
                return None

            choice = choices[0]
            message = choice.get("message", {})
            content = (message.get("content") or "").strip()
            finish_reason = choice.get("finish_reason", "")

            if not content:
                # 推理型模型（如 deepseek-v4-pro）的 reasoning_content 会消耗
                # max_tokens 预算，预算不足时 content 为空
                reasoning = message.get("reasoning_content")
                if reasoning:
                    logger.warning(
                        f"LLM 输出为空（推理模型 token 预算耗尽: "
                        f"finish_reason={finish_reason}, reasoning长度={len(reasoning)}），"
                        f"请调大 llm_max_tokens（当前 {settings.llm_max_tokens}）"
                    )
                else:
                    logger.warning(f"LLM 返回空内容 (finish_reason={finish_reason})")
                return None

            if finish_reason == "length":
                logger.warning("LLM 输出被 max_tokens 截断，结果可能不完整")

            return content
        except Exception as e:
            logger.warning(f"LLM API 调用异常: {type(e).__name__}: {e}")
            return None


# ═══════════════════════════════════════════
# 预置已知关系的语义映射（供自动初始化使用）
# ═══════════════════════════════════════════

_PRESET_SEMANTICS: dict[str, dict] = {
    "MED_TREATS": {
        "display_name": "治疗",
        "description": "药物治疗某种疾病的关系，表示该药物用于治疗该疾病",
        "source_hint": "Drug",
        "target_hint": "Disease",
        "cardinality": "many_to_many",
        "symmetry": "asymmetric",
        "transitivity": "intransitive",
    },
    "MED_HAS_SIDE_EFFECT": {
        "display_name": "副作用",
        "description": "药物产生某副作用的关系，表示服药后可能引发该副作用",
        "source_hint": "Drug",
        "target_hint": "SideEffect",
        "cardinality": "many_to_many",
        "symmetry": "asymmetric",
        "transitivity": "intransitive",
    },
    "MED_MANIFESTS_IN": {
        "display_name": "症状表现于",
        "description": "症状在某个身体部位表现的关系",
        "source_hint": "Symptom",
        "target_hint": "BodyPart",
        "cardinality": "many_to_many",
        "symmetry": "asymmetric",
        "transitivity": "intransitive",
    },
    "MED_AFFECTS": {
        "display_name": "影响",
        "description": "疾病影响某个身体部位的关系",
        "source_hint": "Disease",
        "target_hint": "BodyPart",
        "cardinality": "many_to_many",
        "symmetry": "asymmetric",
        "transitivity": "intransitive",
    },
    "MED_HAS_SYMPTOM": {
        "display_name": "症状",
        "description": "疾病表现出某症状的关系",
        "source_hint": "Disease",
        "target_hint": "Symptom",
        "cardinality": "many_to_many",
        "symmetry": "asymmetric",
        "transitivity": "intransitive",
    },
    "MED_BELONGS_TO": {
        "display_name": "归属",
        "description": "实体归属于某分类的关系",
        "cardinality": "many_to_one",
        "symmetry": "asymmetric",
        "transitivity": "intransitive",
    },
    "MED_HAS_SUBCLASS": {
        "display_name": "子类",
        "description": "父类包含子类的关系",
        "cardinality": "one_to_many",
        "symmetry": "asymmetric",
        "transitivity": "transitive",
    },
    "MED_SUB_CLASS_OF": {
        "display_name": "属于",
        "description": "子类归属于父类的分类关系（子类 → 父类）",
        "source_hint": "Disease",
        "target_hint": "Disease",
        "cardinality": "many_to_one",
        "symmetry": "asymmetric",
        "transitivity": "transitive",
    },
}


def get_preset_semantics(rel_type: str) -> dict | None:
    """获取预置的关系语义映射。"""
    return _PRESET_SEMANTICS.get(rel_type)


def get_all_preset_relation_types() -> set[str]:
    """获取所有预置的关系类型。"""
    return set(_PRESET_SEMANTICS.keys())


def _llm_configured() -> bool:
    """检查 LLM API 是否已配置。"""
    return bool(
        settings.llm_api_key
        and settings.llm_api_key != "sk-xxx"
        and settings.llm_api_base
    )
