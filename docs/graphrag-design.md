# GraphRAG 智能问答系统设计文档

> 版本：v3.8
> 参考：GraphRAG 系统架构设计（6层管道）
> 最后更新：2026-07-27

---

## 1. 架构总览

```
用户问题
   │
   ├── L1 结果缓存命中？──是──→ 直接返回缓存结果（TTL 5min）
   │
   ├── LLM 已配置？───是──→ LLM 路径（6层管道）
   │                        │
   │                        ├─ 1. 意图识别+实体抽取     (LLM)
   │                        ├─ 2. 实体链接              (Neo4j)
   │                        ├─ 3. Schema+语义检索       (并行执行)
   │                        │     ├─ Schema 查询  (Neo4j, 缓存, 标签+关系双重过滤)
   │                        │     └─ 语义查询    (SQLite, 缓存, 主动失效)
   │                        ├─ 4. Cypher生成            (LLM, Few-shot注入, 意图感知)
   │                        ├─ 5. 校验+修复×2           (EXPLAIN+LLM)
   │                        └─ 6. 执行+答案合成          (Neo4j+LLM, 意图感知)
   │
   └── LLM 不可用或失败──→ 规则引擎路径（降级）
                            ├─ 实体关键词匹配
                            ├─ 全向关系查询
                            └─ 模板化自然语言输出
```

与 v3.7 的差异：入口增加 L1 结果缓存；第 3 层并行化；Schema 双重过滤；第 4 层注入 Few-shot；语义缓存主动失效；第 6 层意图感知。

---

## 2. 各层详细设计

### 2.1 L1 查询结果缓存（新增）

| 项 | 设计 |
|----|------|
| 触发时机 | `ask()` 入口，LLM 路径之前 |
| 缓存 Key | `f"{prefix}:{question.strip().lower()}"` |
| TTL | 5 分钟 |
| 命中 | 直接返回 `{answer, cypher, raw_data}`，跳过全部管道 |
| 未命中 | 走正常管道，成功后写入缓存 |

```python
self._result_cache: dict[str, tuple[float, dict]]
```

---

### 2.2 第 1 层：意图识别 + 实体抽取

**方法**: `_extract_intent_and_entities(question, prefix)`

**输出**:
```json
{
  "intent": "lookup|aggregate|path|compare|unknown",
  "entities": ["肠道", "急性胃肠炎"],
  "question_type": "用户具体想问什么"
}
```

**意图分类**（与下游联动）:

| 意图 | 触发词 | Cypher 特征 | 答案合成提示（新增） |
|------|--------|-------------|---------------------|
| lookup | "是什么""和什么有关" | MATCH 关联查询 | "列出所有关联关系" |
| aggregate | "多少""几个" | count/collect | "给出统计数字" |
| path | "什么关系""如何关联" | 路径查询 | "描述关联路径" |
| compare | "区别""不同" | 双实体对比 | "对比差异" |
| unknown | 其他 | 通用生成 | 通用提示 |

**意图传递**（新增）: `intent` 同时传给第 4 层（Cypher 生成 prompt）和第 6 层（答案合成 prompt）。

**JSON 解析策略**（三级兜底）:
1. 提取 ` ```json ... ``` ` 代码块
2. 直接 `json.loads()` 整个文本
3. 括号计数逐字符扫描找到第一个完整 JSON 对象

---

### 2.3 第 2 层：实体链接

**方法**: `_link_entities(entities, prefix)`

**输出**: `(格式化文本, 匹配到的标签列表)`

```
对每个实体名:
  → Cypher: MATCH (n) WHERE n.name CONTAINS $name
  → 返回: n.name, labels(n)
  → 提取: 匹配到的标签（以 prefix 开头）
```

标签列表用于第 3 层 Schema 双重过滤。

---

### 2.4 第 3 层：Schema + 语义检索

#### 2.4.1 并行执行（新增）

Schema 查询与语义查询互不依赖，使用 `ThreadPoolExecutor` 并行：

```python
with ThreadPoolExecutor(max_workers=2) as pool:
    f1 = pool.submit(self._get_schema_summary, prefix, linked_labels)
    f2 = pool.submit(self._build_semantics_section, prefix)
    schema_context = f1.result()
    semantics_section = f2.result()
```

**收益**: 减少 100~200ms 串行等待。

#### 2.4.2 Schema 检索（双重过滤，增强）

**方法**: `_get_schema_summary(prefix, linked_labels)`

**缓存**: TTL 30 分钟，缓存原始查询结果

**过滤策略**:

| 过滤维度 | v3.7 | v3.8 |
|----------|------|------|
| 标签 | 只保留命中标签 | 只保留命中标签（不变） |
| 关系类型 | 全量保留 | **只保留命中标签之间实际存在的关系**（新增） |

关系类型过滤 Cypher（新增）:
```cypher
MATCH (a)-[r]->(b)
WHERE any(l IN labels(a) WHERE l IN $linked_labels)
  AND any(l IN labels(b) WHERE l IN $linked_labels)
RETURN DISTINCT type(r) AS rel_type
```

**效果**: 50 标签 / 100 关系的系统，问题只涉及 2 个标签时，关系类型从 100 降到 3~5 个。

#### 2.4.3 语义检索（主动失效，增强）

**方法**: `_build_semantics_section(prefix)`

**缓存**: TTL 30 分钟 + **主动失效机制**（新增）

**主动失效**:
```python
# SystemService 写入语义后调用
QueryService.invalidate_semantics_cache(prefix)
```

| 操作 | 触发失效 |
|------|----------|
| `upsert_relation_semantic` | 清除该 prefix 的语义缓存 |
| `delete_relation_semantic` | 清除该 prefix 的语义缓存 |
| `import_service` 导入完成 | 清除该 prefix 的 Schema 缓存 + 语义缓存 |

**效果**: 用户修改语义后立即生效，无需等待 30 分钟。

---

### 2.5 第 4 层：Cypher 生成（Few-shot 注入，增强）

**方法**: `_generate_cypher(question, intent, question_type, linked, schema, semantics, prefix)`

**Prompt 组成**（v3.8 新增第 3 项）:
1. 查询意图提示（根据 intent 给出 Cypher 生成方向）
2. 图谱 Schema（双重过滤后）
3. **Few-shot 示例（新增）**：从成功案例库检索最相关的 1~2 个 `问题 → Cypher` 对
4. 关系语义说明（Markdown 表格）
5. 匹配到的实体
6. 硬性规则（前缀约束、CANNOT_GENERATE 兜底等）
7. 用户原始问题

**Few-shot 示例来源**:
- 预置示例（针对医疗系统手写 5~10 个典型案例）
- 成功案例回流（校验通过 + 结果非空的查询自动入库）

**示例格式**:
```
## 参考示例
问题：阿司匹林治疗什么疾病
Cypher：MATCH (d:MED_Drug)-[r:MED_TREATS]->(dis:MED_Disease)
        WHERE d.name CONTAINS '阿司匹林' RETURN DISTINCT dis.name
```

**存储**: `backend/data/fewshots.jsonl`，启动时加载到内存。

---

### 2.6 第 5 层：校验 + 修复

#### 校验

**方法**: `_validate_cypher(cypher)`

1. 安全检查: 禁止 `CREATE/MERGE/DELETE/SET/REMOVE`
2. 语法校验: `EXPLAIN <cypher>`

#### 修复

**方法**: `_repair_cypher(...)`

- 错误信息回灌 LLM，最多重试 2 次
- 3 次全部失败 → 返回失败阶段标记，降级规则引擎

---

### 2.7 第 6 层：执行 + 答案合成（意图感知，增强）

#### 执行

`self._repo._run(cypher)`，结果裁剪前 20 行。

#### 答案合成

**方法**: `_synthesize_answer(question, data, prefix, intent)`（新增 intent 参数）

**意图感知 Prompt**（新增）: 根据 intent 在 Prompt 中追加针对性指令：

```
## 回答风格
{intent_hint}    # lookup→"列出所有关联关系" / aggregate→"先给数字再列举" / ...
```

**核心原则不变**: 严格忠实于数据，禁止添加任何图谱结果中没有的信息。

---

## 3. 降级路径：规则引擎

**触发条件**: LLM 路径任何环节失败（未配置 / 意图提取失败 / Cypher 生成失败 / 校验全部失败）

**流程**:
1. `_find_node_by_question()`: 最长子串匹配实体名
2. Cypher 全向关系查询
3. 按关系类型和方向分组
4. 意图方向判断 → `_format_rel_groups()` 生成自然语句
5. 未配置语义的关系类型给出提示

---

## 4. 缓存设计（三层）

| 层级 | 缓存 | Key | TTL | 失效策略 |
|------|------|-----|-----|----------|
| L1 | 查询结果缓存（新增） | `prefix:question` | 5 min | 时间过期 |
| L2 | Schema 缓存 | prefix | 30 min | 时间过期 + **导入后主动失效** |
| L3 | 语义缓存 | prefix | 30 min | 时间过期 + **语义修改后主动失效** |

**缓存位置**: `QueryService` 实例内存（进程级）

---

## 5. Prompt 大小控制

| 段落 | 控制策略 |
|------|----------|
| Schema | 双重过滤（标签 + 关系类型） |
| 语义 | 全量（通常较小） |
| Few-shot | 最多 2 个示例（新增） |
| 实体链接 | 最多 5 个候选/实体 |
| 查询结果 | 最多 20 行，JSON 裁剪 3000 字符 |
| 答案合成 | 结果 JSON 裁剪 3000 字符 |

**监控**: 估算 token > 8000 时 `logger.warning`。

---

## 6. 安全设计

| 措施 | 实现 |
|------|------|
| 只读操作 | `_validate_cypher` 拦截写操作 |
| 注入防护 | 参数化查询（`$name`, `$prefix`） |
| 输出净化 | 纯 Cypher，禁止代码块包裹 |
| 结果忠实 | 答案合成禁止添加领域知识 |

---

## 7. 性能指标

| 指标 | v3.7 | v3.8 | 说明 |
|------|------|------|------|
| LLM 调用次数 | 3 次 | 3 次 | 意图 + 生成 + 合成 |
| LLM 调用（修复） | 4~5 次 | 4~5 次 | +修复循环 |
| Neo4j 查询 | 3~5 次 | 3~5 次 | 缓存命中时 2~3 次 |
| 重复问题延迟 | 2~5s | **~10ms** | L1 缓存命中直接返回 |
| Schema+语义检索 | 串行 ~200ms | **并行 ~100ms** | ThreadPoolExecutor |
| 语义修改生效 | 最多 30min | **立即** | 主动失效 |
| Cypher 准确率 | 依赖 LLM | **提升** | Few-shot 注入 |

---

## 8. 已知限制与改进方向

| 限制 | 影响 | 改进方向 |
|------|------|----------|
| 缓存均在内存 | 重启丢失 | 可选：Redis 持久化 |
| 意图识别 5 类 | 复杂查询分类可能不准 | 增加类别或细粒度分类 |
| 实体链接仅 CONTAINS | 模糊匹配精度有限 | 可选：向量相似度匹配 |
| Few-shot 静态加载 | 新案例需重启 | 可选：热加载 / 向量检索示例 |
| 结果缓存无意图校验 | 相似问题可能误命中 | 缓存 Key 加入 intent |
| 无可观测性 Trace | 失败案例难追踪 | 可选：结构化日志 + 失败案例入库 |

---

## 9. 文件结构

```
backend/services/query_service.py
├── QueryService
│   ├── ask()                              # 公共入口（L1 结果缓存检查）
│   ├── _ask_llm()                         # LLM 路径（6层管道）
│   │   ├── _extract_intent_and_entities() # 第1层：意图+实体
│   │   ├── _link_entities()               # 第2层：实体链接
│   │   ├── _get_schema_summary()          # 第3层：Schema（缓存+双重过滤）
│   │   ├── _build_semantics_section()     # 第3层：语义（缓存+主动失效）
│   │   ├── _generate_cypher()             # 第4层：Cypher（Few-shot注入）
│   │   ├── _validate_cypher()             # 第5层：校验
│   │   ├── _repair_cypher()               # 第5层：修复
│   │   └── _synthesize_answer()           # 第6层：答案合成（意图感知）
│   ├── _ask_rules()                       # 规则引擎路径（降级）
│   ├── invalidate_semantics_cache()       # 语义缓存主动失效（新增）
│   ├── invalidate_schema_cache()          # Schema 缓存主动失效（新增）
│   ├── _get_cached_result()               # L1 结果缓存读（新增）
│   ├── _set_cached_result()               # L1 结果缓存写（新增）
│   └── _call_llm()                        # LLM API 调用
├── backend/data/fewshots.jsonl            # Few-shot 示例库（新增）
└── _PRESET_SEMANTICS                      # 预置语义映射
```
