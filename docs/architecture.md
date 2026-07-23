# 疾病本体可视化与查询系统 - 架构规划文档

> 版本: v1.0 | 日期: 2026-07-22 | 状态: 规划阶段

---

## 目录

1. [项目概述](#1-项目概述)
2. [数据模型分析](#2-数据模型分析)
3. [系统架构总览](#3-系统架构总览)
4. [前端设计](#4-前端设计)
5. [后端设计](#5-后端设计)
6. [API 接口设计](#6-api-接口设计)
7. [界面布局设计](#7-界面布局设计)
8. [技术选型](#8-技术选型)
9. [项目目录结构](#9-项目目录结构)
10. [开发实施路线](#10-开发实施路线)

---

## 1. 项目概述

### 1.1 项目目标

基于现有的 Neo4j 疾病本体知识图谱，构建一个 **Web 可视化交互平台**，提供以下核心能力：

- **本体浏览**：树形展开查看本体类、实例、属性
- **关系图谱**：交互式力导向图展示整个知识图谱
- **智能问答**：基于 GraphRAG 的自然语言查询

### 1.2 现有基础

- **数据库**：Neo4j (本地 `bolt://localhost:7687`)
- **已有代码**：`test_graphrag.py` — 基于 LangChain 的 GraphRAG 命令行查询工具
- **LLM 服务**：可通过 OpenAI 兼容 API 调用 `glm-5.2`

---

## 2. 数据模型分析

### 2.1 节点类型（5类）

| 节点标签 | 数量 | 属性 |
|---------|------|------|
| **Disease** (疾病) | 19 | `name`, `icd_prefix`, `definition` |
| **Symptom** (症状) | 14 | `name`, `severity`, `body_region`, `description` |
| **Drug** (药物) | 8 | `name`, `generic_name`, `brand_name`, `category`, `dosage`, `dosage_form`, `frequency`, `max_daily` |
| **BodyPart** (身体部位) | 7 | `name`, `location` |
| **SideEffect** (副作用) | 7 | `name`, `severity`, `frequency` |

### 2.2 关系类型（7类）

| 关系类型 | 方向 | 数量 | 语义 |
|---------|------|------|------|
| `SUB_CLASS_OF` | `(child:Disease)→(parent:Disease)` | 16 | 疾病层级分类（如"普通感冒"→"呼吸系统疾病"） |
| `MANIFESTS_IN` | `(s:Symptom)→(d:Disease)` | 42 | 症状出现在某疾病中 |
| `TREATS` | `(d:Drug)→(dis:Disease)` | 20 | 药物可治疗某疾病 |
| `CONTRAINDICATED_WITH` | `(d:Drug)→(c)` | 5 | 药物禁忌 |
| `CAN_SUBSTITUTE` | 双向 | 6 | 药物间可替代 |
| `AFFECTS` | `(d:Disease)→(b:BodyPart)` | 11 | 疾病影响身体部位 |
| `HAS_SIDE_EFFECT` | `(d:Drug)→(se:SideEffect)` | 12 | 药物有副作用 |

### 2.3 数据特征总结

- 疾病有 **层级结构** (SUB_CLASS_OF)，顶层大类无直接症状
- 所有属性为 **字符串类型**，无数值区间
- 关系本身 **无额外属性**
- 节点名称可能存在部分匹配需求（如"感冒"匹配"普通感冒"）

---

## 3. 系统架构总览

```
┌──────────────────────────────────────────────────────────────────┐
│                        前端 (React SPA)                          │
│  ┌─────────────┐  ┌──────────────────┐  ┌───────────────────┐   │
│  │ 本体浏览器   │  │   图谱可视化      │  │   智能问答面板     │   │
│  │ (Tree View) │  │ (Force Graph)    │  │ (Chat Interface)  │   │
│  └─────────────┘  └──────────────────┘  └───────────────────┘   │
│                         │  HTTP/REST                             │
└─────────────────────────┼────────────────────────────────────────┘
                          │
┌─────────────────────────┼────────────────────────────────────────┐
│                    后端 (FastAPI)                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    路由层 (Routers)                        │   │
│  │   ontology_router   │   graph_router   │   query_router   │   │
│  └──────────┬──────────┴───────┬──────────┴───────┬──────────┘   │
│  ┌──────────┴──────────┐───────┴──────────┐───────┴──────────┐   │
│  │                    服务层 (Services)                        │   │
│  │   OntologyService   │  GraphService    │  QueryService     │   │
│  └──────────┬──────────┴───────┬──────────┴───────┬──────────┘   │
│  ┌──────────┴──────────────────┴──────────────────┴──────────┐   │
│  │                    数据访问层 (Repository)                  │   │
│  │                   Neo4jRepository                          │   │
│  └──────────────────────────┬─────────────────────────────────┘   │
└─────────────────────────────┼─────────────────────────────────────┘
                              │  Bolt Protocol
                    ┌─────────┴─────────┐
                    │   Neo4j Database  │
                    │ (localhost:7687)  │
                    └───────────────────┘
```

**架构原则**：
- **三层架构**：Router → Service → Repository，职责分离清晰
- **Repository 层封装所有 Cypher 查询**，避免散落各处的字符串拼接
- **Service 层负责业务逻辑**，如数据聚合、Schema 构建、LLM 调用编排
- **Router 层只做参数校验和响应格式化**

---

## 4. 前端设计

### 4.1 页面布局

```
┌──────────────────────────────────────────────────────────────────┐
│  🏥 疾病本体知识图谱平台                                          │
├────────────┬──────────────────────────┬───────────────────────────┤
│            │                          │                           │
│  本体浏览器 │      图谱可视化           │     智能问答面板           │
│  (300px)   │      (flex-1)            │     (380px)               │
│            │                          │                           │
│  ▼ Disease │   ┌──────────────────┐   │  ┌─────────────────────┐  │
│    ├ 普通感冒│   │                  │   │  │ 用户: 感冒有什么症状  │  │
│    │  ├ name │   │   ○ → ○ → ○     │   │  │ 系统: 普通感冒的症状  │  │
│    │  ├ icd  │   │   ↓   ↓         │   │  │ 包括...             │  │
│    │  └ def  │   │   ○ ← ○         │   │  └─────────────────────┘  │
│    ├ 急性胃炎│   │                  │   │  ┌─────────────────────┐  │
│  ▼ Symptom  │   │  (力导向图)       │   │  │ 💬 输入问题...       │  │
│  ▼ Drug     │   │                  │   │  └─────────────────────┘  │
│  ▼ BodyPart │   └──────────────────┘   │                           │
│  ▼ SideEff  │                          │  节点详情 (点击展开)       │
│            │                          │  ┌─────────────────────┐  │
│            │  图例筛选                  │  │ 类型: Disease       │  │
│            │  ☑ Disease ☑ Symptom     │  │ 名称: 普通感冒       │  │
│            │  ☑ Drug    ☑ BodyPart    │  │ ICD: A-Z            │  │
│            │  ☑ SideEffect            │  │ 定义: ...           │  │
│            │                          │  │ 关联症状: ...        │  │
│            │                          │  └─────────────────────┘  │
├────────────┴──────────────────────────┴───────────────────────────┤
│  状态栏: 节点 55 | 关系 112 | Neo4j 已连接                         │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 核心组件树

```
App
├── Layout (Ant Design Layout)
│   ├── Header (顶部导航)
│   │   ├── Logo + 标题
│   │   └── 连接状态指示器
│   │
│   ├── Sider (左侧 - 本体浏览器)
│   │   └── OntologyBrowser
│   │       ├── OntologyTree (Ant Design Tree)
│   │       │   ├── NodeTypeGroup (疾病/症状/药物/部位/副作用)
│   │       │   ├── NodeInstance (具体实例，可展开)
│   │       │   │   ├── PropertyItem (name, definition...)
│   │       │   │   └── RelationshipList (该节点的关系)
│   │       │   │       └── RelationshipItem (关系类型 → 目标节点)
│   │       │   └── RelationshipTypeGroup (关系类型维度)
│   │       │       └── RelationshipInstance (具体关系实例)
│   │       └── SearchBar (节点搜索)
│   │
│   ├── Content (中间 - 图谱可视化)
│   │   └── GraphCanvas
│   │       ├── ForceGraph (vis-network / cytoscape)
│   │       ├── GraphControls (缩放、居中、导出)
│   │       └── LegendFilter (图例 + 类型筛选开关)
│   │
│   └── Drawer/Aside (右侧 - 智能问答 + 详情)
│       ├── QueryPanel
│       │   ├── MessageList (对话记录)
│       │   ├── CypherDisplay (显示生成的 Cypher)
│       │   └── InputBox (问题输入框)
│       └── NodeDetailPanel (点击节点时显示)
│           ├── PropertyTable (属性表)
│           └── RelationshipCard (关联关系卡片)
│
└── Footer (状态栏)
```

### 4.3 交互流程

```
[点击本体树中的节点]
    │
    ├──→ 中间图谱：高亮该节点 + 展开其一级邻居
    └──→ 右侧面板：展示节点详情

[点击图谱中的节点]
    │
    ├──→ 左侧树：定位并展开到该节点
    └──→ 右侧面板：展示节点详情

[在图谱中拖拽/缩放]
    └──→ 局部更新视图，不重新请求数据

[在输入框提交问题]
    │
    ├──→ 后端 GraphRAG 处理
    ├──→ 返回：自然语言答案 + Cypher + 相关子图数据
    ├──→ 聊天面板：展示回答和 Cypher
    └──→ 图谱：可选地高亮查询相关的节点/路径
```

### 4.4 状态管理

采用 **React Context + useReducer** 轻量方案（此项目规模不需要 Redux/Zustand）：

```typescript
// 全局状态结构
interface AppState {
  // 本体数据
  ontology: {
    nodeTypes: NodeTypeInfo[];       // 节点类型列表
    relationshipTypes: RelTypeInfo[]; // 关系类型列表
    selectedNode: NodeDetail | null;  // 当前选中的节点
    expandedKeys: string[];           // 树展开的 key
  };

  // 图谱数据
  graph: {
    nodes: GraphNode[];              // 当前可视化的节点
    edges: GraphEdge[];              // 当前可视化的边
    visibleTypes: Set<string>;       // 可见的节点类型（图例筛选）
    layout: 'force' | 'hierarchical';
  };

  // 查询面板
  query: {
    messages: ChatMessage[];         // 对话历史
    loading: boolean;                // 查询加载中
    currentQuery: string;            // 当前输入
  };

  // 系统
  system: {
    neo4jConnected: boolean;
    error: string | null;
  };
}
```

---

## 5. 后端设计

### 5.1 架构分层

```
backend/
├── main.py                    # FastAPI 应用入口 + CORS 配置
├── config.py                  # 配置管理（Neo4j 连接、LLM API）
├── routers/                   # 路由层
│   ├── __init__.py
│   ├── ontology_router.py     # /api/ontology/*
│   ├── graph_router.py        # /api/graph/*
│   └── query_router.py        # /api/query/*
├── services/                  # 服务层
│   ├── __init__.py
│   ├── ontology_service.py    # 本体数据聚合、Schema 构建
│   ├── graph_service.py       # 图谱数据查询、子图提取
│   └── query_service.py       # LLM + GraphRAG 编排
├── repositories/              # 数据访问层
│   ├── __init__.py
│   └── neo4j_repository.py    # 封装所有 Cypher 查询
├── models/                    # 数据模型 (Pydantic)
│   ├── __init__.py
│   ├── ontology.py            # 本体相关模型
│   ├── graph.py               # 图谱相关模型
│   └── query.py               # 查询相关模型
└── utils/
    ├── __init__.py
    └── cypher_builder.py      # Cypher 查询构建工具
```

### 5.2 分层职责

#### Repository 层 (`neo4j_repository.py`)

封装所有原始 Cypher 查询，**不包含业务逻辑**：

```python
class Neo4jRepository:
    """Neo4j 数据访问层，封装所有 Cypher 查询"""

    # -- 元数据查询 --
    def get_node_labels(self) -> list[dict]
        """获取所有节点标签及其数量"""

    def get_node_label_properties(self, label: str) -> list[dict]
        """获取指定标签的所有属性定义"""

    def get_relationship_types(self) -> list[dict]
        """获取所有关系类型、方向及数量"""

    # -- 实例查询 --
    def get_nodes_by_label(self, label: str, limit=100, offset=0) -> list[dict]
        """分页获取指定标签的节点实例"""

    def get_node_by_id(self, element_id: str) -> dict | None
        """根据 Neo4j elementId 获取节点及其所有属性"""

    def get_node_relationships(self, element_id: str) -> list[dict]
        """获取某节点所有关系（含关系类型、方向、目标节点摘要）"""

    def search_nodes(self, keyword: str, labels=None) -> list[dict]
        """模糊搜索节点（按 name 属性 CONTAINS 匹配）"""

    # -- 图谱查询 --
    def get_full_graph(self, node_limit=200) -> dict
        """获取全量图谱数据（nodes + edges），带数量上限"""

    def get_neighborhood(self, element_id: str, depth=1) -> dict
        """获取某节点的邻域子图（N 跳邻居）"""

    def get_path_between(self, source_id: str, target_id: str, max_depth=3) -> dict
        """查找两节点间的最短路径"""

    # -- 关系查询 --
    def get_relationships_by_type(self, rel_type: str, limit=100) -> list[dict]
        """获取指定关系类型的所有实例"""

    # -- 原始查询（供 QueryService 使用）--
    def execute_cypher(self, cypher: str) -> list[dict]
        """执行自定义 Cypher 查询（仅内部使用，需校验）"""
```

#### Service 层

**OntologyService**：聚合本体元数据

```python
class OntologyService:
    """本体浏览服务"""

    def get_ontology_tree(self) -> OntologyTree:
        """
        构建完整的本体树结构：
        - 一级：节点标签（Disease/Symptom/Drug/BodyPart/SideEffect）
        - 二级：每个标签下的实例列表（含 key 属性摘要）
        - 可选三级：实例的属性列表
        - 可选：按关系类型组织的视图
        """

    def get_node_detail(self, element_id: str) -> NodeDetail:
        """获取节点完整详情：属性 + 所有入/出关系 + 关联节点摘要"""

    def get_relationship_catalog(self) -> list[RelationshipCatalogItem]:
        """获取关系类型目录：每种关系的名称、方向、数量、说明"""

    def search(self, keyword: str) -> SearchResult:
        """全局搜索：匹配节点名、属性值"""
```

**GraphService**：图谱可视化数据

```python
class GraphService:
    """图谱可视化服务"""

    def get_overview_graph(self) -> GraphData:
        """
        获取全量图谱数据，格式为 {nodes: [...], edges: [...]}，
        适用于首次加载时的力导向图渲染。
        nodes 包含：id, label, type, name, color(按类型)
        edges 包含：source, target, type, label
        """

    def expand_node(self, element_id: str) -> GraphData:
        """展开某节点的一级邻居，返回增量数据用于图谱追加"""

    def get_subgraph_by_types(self, node_types: list[str]) -> GraphData:
        """按选中的节点类型筛选子图"""

    def get_path_visualization(self, source_id: str, target_id: str) -> GraphData | None:
        """计算最短路径并返回可视化数据"""
```

**QueryService**：GraphRAG 问答

```python
class QueryService:
    """智能问答服务（GraphRAG）"""

    def ask(self, question: str) -> QueryResult:
        """
        核心流程：
        1. 将自然语言问题 + Schema Prompt 发给 LLM
        2. LLM 生成 Cypher 查询
        3. 在 Neo4j 执行 Cypher
        4. 将查询结果 + 原始问题发给 LLM 生成自然语言回答
        5. 返回：answer + cypher + raw_data
        """

    def get_schema_for_prompt(self) -> str:
        """构建注入 LLM Prompt 的 Schema 描述文本"""
```

#### Router 层

```python
# ontology_router.py
GET    /api/ontology/tree              # 获取本体树
GET    /api/ontology/nodes/{id}        # 获取节点详情
GET    /api/ontology/relationships     # 获取关系目录
GET    /api/ontology/search?q=xxx      # 搜索节点

# graph_router.py
GET    /api/graph/overview             # 获取全量图谱数据
GET    /api/graph/neighbors/{id}       # 获取节点邻域
GET    /api/graph/expand/{id}          # 展开节点
GET    /api/graph/path?from=x&to=y     # 最短路径

# query_router.py
POST   /api/query                      # 自然语言问答
POST   /api/query/stream               # 流式问答 (SSE，可选)
GET    /api/query/schema               # 获取 Schema Prompt
```

### 5.3 可扩展性设计

| 扩展点 | 设计 |
|--------|------|
| **新增节点/关系类型** | Repository 的泛型方法（通过 label/type 参数化），无需改代码 |
| **新增查询类型** | 在对应 Service 加方法，在 Router 加端点即可 |
| **切换 LLM** | `QueryService` 依赖抽象的 LLM 接口，只需改配置 |
| **新增数据库** | Repository 接口化，可扩展为支持多数据源 |
| **性能优化** | Repository 可加查询缓存、分页；图谱可加懒加载 |

---

## 6. API 接口设计

### 6.1 通用约定

- 基础路径：`/api`
- 响应格式：
  ```json
  {
    "code": 0,
    "data": { ... },
    "message": "success"
  }
  ```
- 错误格式：
  ```json
  {
    "code": 40001,
    "data": null,
    "message": "节点不存在"
  }
  ```

### 6.2 本体接口

#### `GET /api/ontology/tree`

获取完整本体树结构。

**响应示例**：
```json
{
  "code": 0,
  "data": {
    "node_types": [
      {
        "label": "Disease",
        "count": 19,
        "properties": ["name", "icd_prefix", "definition"],
        "instances": [
          {
            "element_id": "4:xxx:0",
            "name": "普通感冒",
            "properties": {
              "icd_prefix": "J00",
              "definition": "上呼吸道病毒性感染"
            },
            "relationship_count": 5
          }
        ]
      }
    ],
    "relationship_types": [...]
  }
}
```

#### `GET /api/ontology/nodes/{element_id}`

获取节点完整详情。

**响应示例**：
```json
{
  "code": 0,
  "data": {
    "element_id": "4:xxx:0",
    "labels": ["Disease"],
    "properties": { "name": "普通感冒", "icd_prefix": "J00", "definition": "..." },
    "incoming_relationships": [
      { "type": "MANIFESTS_IN", "source": { "element_id": "...", "name": "咳嗽", "label": "Symptom" } }
    ],
    "outgoing_relationships": [
      { "type": "AFFECTS", "target": { "element_id": "...", "name": "咽喉", "label": "BodyPart" } },
      { "type": "SUB_CLASS_OF", "target": { "element_id": "...", "name": "呼吸系统疾病", "label": "Disease" } }
    ]
  }
}
```

### 6.3 图谱接口

#### `GET /api/graph/overview`

获取全量图谱数据。

**响应示例**：
```json
{
  "code": 0,
  "data": {
    "nodes": [
      { "id": "4:xxx:0", "label": "普通感冒", "type": "Disease", "color": "#FF6B6B", "count": 19 },
      { "id": "4:yyy:1", "label": "咳嗽", "type": "Symptom", "color": "#4ECDC4", "count": 14 }
    ],
    "edges": [
      { "id": "r1", "source": "4:yyy:1", "target": "4:xxx:0", "type": "MANIFESTS_IN", "label": "出现在" }
    ],
    "meta": {
      "total_nodes": 55,
      "total_edges": 112
    }
  }
}
```

#### `GET /api/graph/neighbors/{element_id}?depth=1`

获取节点邻域子图。

### 6.4 查询接口

#### `POST /api/query`

**请求**：
```json
{
  "question": "感冒有什么症状"
}
```

**响应**：
```json
{
  "code": 0,
  "data": {
    "answer": "普通感冒的常见症状包括：鼻塞流涕、咽痛、咳嗽、头痛、乏力、发热。",
    "cypher": "MATCH (s:Symptom)-[:MANIFESTS_IN]->(d:Disease) WHERE d.name CONTAINS '感冒' RETURN s.name, s.severity, s.description",
    "raw_data": [
      { "s.name": "鼻塞流涕", "s.severity": "轻", "s.description": "鼻腔分泌物增多" }
    ],
    "related_graph": {
      "nodes": [...],
      "edges": [...]
    }
  }
}
```

---

## 7. 界面布局设计

### 7.1 整体布局

采用 **三栏布局**，左侧本体浏览器 + 中间图谱 + 右侧智能问答 / 节点详情：

| 区域 | 宽度 | 功能 |
|------|------|------|
| 左侧面板 | 320px (可拖拽调整) | 本体树 + 搜索 |
| 中间主区域 | flex-1 | 图谱可视化 |
| 右侧面板 | 400px (可收起) | 智能问答 / 节点详情 |

### 7.2 左侧：本体浏览器

**视图模式切换**：
- **按节点类型浏览**（默认）：展开 Disease/Symptom/Drug/BodyPart/SideEffect → 每个类型下列出实例
- **按关系类型浏览**：展开 7 种关系 → 每种下列出来源→目标的实例

**交互**：
- 点击节点类型标题 → 折叠/展开
- 点击实例名 → 中间图谱高亮该节点 + 右侧展示详情
- 点击属性 → 无特殊动作（只读展示）
- 搜索框 → 全局模糊搜索，匹配后定位到对应树节点

### 7.3 中间：图谱可视化

**功能**：
- 力导向布局，节点按类型着色
- 支持拖拽节点、缩放画布
- 点击节点 → 展开/高亮其邻居
- 双击节点 → 以该节点为中心重新布局
- 图例面板：勾选/取消 节点类型以筛选显示

**交互细节**：
- 悬停节点 → tooltip 显示名称 + 类型
- 悬停边 → tooltip 显示关系类型
- 右键节点 → 菜单（查看详情、扩展邻居、固定位置）

### 7.4 右侧：智能问答 + 详情

**上半部分：智能问答面板**
- 对话气泡式展示问答历史
- 每个回答下方折叠显示 "生成的 Cypher" + "原始数据"
- 输入框支持 Enter 发送，Shift+Enter 换行

**下半部分（或切换 tab）：节点详情面板**
- 当点击节点时自动填充
- 属性以表格形式展示
- 关系以卡片列表展示，每张卡片可点击跳转到目标节点

---

## 8. 技术选型

### 8.1 前端

| 层面 | 技术 | 原因 |
|------|------|------|
| **框架** | React 18 + TypeScript | 生态丰富，社区活跃 |
| **构建工具** | Vite | 快速开发启动，HMR |
| **UI 组件库** | Ant Design 5 | 适合数据密集型应用，Tree/Table/Form 组件完善 |
| **图谱可视化** | vis-network (或 cytoscape.js) | vis-network 上手简单，API 友好；cytoscape 更灵活但复杂 |
| **HTTP 客户端** | axios | 拦截器、错误处理方便 |
| **状态管理** | React Context + useReducer | 项目规模适中，无需引入 Redux |

### 8.2 后端

| 层面 | 技术 | 原因 |
|------|------|------|
| **框架** | FastAPI | 异步支持、自动 OpenAPI 文档、类型校验 |
| **数据库驱动** | neo4j (官方 Python driver) | 直接 Cypher 查询，性能最好 |
| **LLM 集成** | langchain + langchain-openai | 复用已有 GraphCypherQAChain 逻辑 |
| **数据校验** | Pydantic v2 | FastAPI 原生集成 |
| **配置管理** | pydantic-settings | 环境变量 / .env 管理 |

### 8.3 不额外引入的技术

- 不使用数据库 ORM（直接 Cypher 查询）
- 不引入消息队列（当前规模不需要）
- 不引入用户认证（本地单用户使用）

---

## 9. 项目目录结构

```
DiseaseOntology/
│
├── docs/
│   └── architecture.md              # 本规划文档
│
├── backend/
│   ├── main.py                      # FastAPI 入口
│   ├── config.py                    # 配置管理
│   ├── requirements.txt             # Python 依赖
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── ontology_router.py       # /api/ontology/*
│   │   ├── graph_router.py          # /api/graph/*
│   │   └── query_router.py          # /api/query/*
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ontology_service.py
│   │   ├── graph_service.py
│   │   └── query_service.py
│   │
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── neo4j_repository.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── ontology.py
│   │   ├── graph.py
│   │   └── query.py
│   │
│   └── utils/
│       ├── __init__.py
│       └── cypher_builder.py
│
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   │
│   ├── src/
│   │   ├── main.tsx                 # 入口
│   │   ├── App.tsx                  # 根组件 + 布局
│   │   ├── api/                     # API 调用封装
│   │   │   ├── client.ts            # axios 实例 + 拦截器
│   │   │   ├── ontology.ts          # 本体相关 API
│   │   │   ├── graph.ts             # 图谱相关 API
│   │   │   └── query.ts             # 查询相关 API
│   │   │
│   │   ├── store/                   # 状态管理
│   │   │   ├── AppContext.tsx
│   │   │   ├── types.ts
│   │   │   └── reducer.ts
│   │   │
│   │   ├── components/
│   │   │   ├── Layout/
│   │   │   │   ├── AppHeader.tsx        # 顶部导航
│   │   │   │   └── StatusBar.tsx        # 底部状态栏
│   │   │   │
│   │   │   ├── OntologyBrowser/         # 左侧本体浏览器
│   │   │   │   ├── OntologyBrowser.tsx  # 容器组件
│   │   │   │   ├── OntologyTree.tsx     # Ant Design Tree
│   │   │   │   ├── NodeTypeGroup.tsx    # 节点类型分组
│   │   │   │   ├── InstanceItem.tsx     # 实例节点
│   │   │   │   └── SearchBar.tsx        # 搜索框
│   │   │   │
│   │   │   ├── GraphCanvas/             # 中间图谱
│   │   │   │   ├── GraphCanvas.tsx      # 容器组件
│   │   │   │   ├── ForceGraph.tsx       # vis-network 封装
│   │   │   │   ├── GraphControls.tsx    # 缩放/居中控制
│   │   │   │   ├── LegendFilter.tsx     # 图例 + 类型筛选项
│   │   │   │   └── NodeTooltip.tsx      # 节点 tooltip
│   │   │   │
│   │   │   └── QueryPanel/              # 右侧查询 + 详情
│   │   │       ├── QueryPanel.tsx       # 容器组件
│   │   │       ├── MessageList.tsx      # 对话列表
│   │   │       ├── ChatBubble.tsx       # 单条消息气泡
│   │   │       ├── CypherDisplay.tsx    # Cypher 展示（可折叠）
│   │   │       ├── InputBox.tsx         # 输入框
│   │   │       ├── NodeDetail.tsx       # 节点详情面板
│   │   │       ├── PropertyTable.tsx    # 属性表格
│   │   │       └── RelationshipCard.tsx # 关系卡片
│   │   │
│   │   ├── hooks/                   # 自定义 Hooks
│   │   │   ├── useOntology.ts
│   │   │   ├── useGraph.ts
│   │   │   └── useQuery.ts
│   │   │
│   │   ├── types/                   # TypeScript 类型定义
│   │   │   ├── ontology.ts
│   │   │   ├── graph.ts
│   │   │   └── query.ts
│   │   │
│   │   └── utils/                   # 工具函数
│   │       ├── graphColors.ts       # 节点类型配色
│   │       └── formatters.ts        # 格式化工具
│   │
│   └── public/
│       └── favicon.ico
│
├── test_graphrag.py                 # 原有命令行工具（保留）
└── requirements.txt                 # 原有依赖（保留）
```

---

## 10. 开发实施路线

### Phase 1：后端核心 API（2-3天）

| 编号 | 任务 | 产出 |
|------|------|------|
| 1.1 | 搭建 FastAPI 项目骨架 | `main.py`, `config.py`, 路由注册 |
| 1.2 | 实现 `Neo4jRepository` | 所有数据查询方法 |
| 1.3 | 实现 `OntologyService` + Router | `/api/ontology/*` 接口可用 |
| 1.4 | 实现 `GraphService` + Router | `/api/graph/*` 接口可用 |
| 1.5 | 迁移 GraphRAG 逻辑到 `QueryService` | `/api/query` 接口可用 |
| 1.6 | 添加 CORS + 错误处理中间件 | |

### Phase 2：前端基础框架（2-3天）

| 编号 | 任务 | 产出 |
|------|------|------|
| 2.1 | 初始化 React + Vite + Ant Design 项目 | 可运行的空项目 |
| 2.2 | 搭建三栏布局 + 状态管理 | `App.tsx`, `AppContext` |
| 2.3 | 封装 API 调用层 | `api/*.ts` |
| 2.4 | 实现数据加载 Hooks | `useOntology`, `useGraph`, `useQuery` |

### Phase 3：核心功能（3-4天）

| 编号 | 任务 | 产出 |
|------|------|------|
| 3.1 | 本体浏览器（树形展开 + 搜索） | `OntologyBrowser` 组件 |
| 3.2 | 图谱可视化（力导向图 + 筛选） | `GraphCanvas` 组件 |
| 3.3 | 节点详情面板 | `NodeDetail` 组件 |
| 3.4 | 智能问答面板 | `QueryPanel` 组件 |
| 3.5 | 三栏联动交互 | 点击树→图谱高亮；点击图谱→详情展示 |

### Phase 4：优化完善（1-2天）

| 编号 | 任务 |
|------|------|
| 4.1 | 图谱交互优化（拖拽、缩放、动画） |
| 4.2 | 响应式适配 / Loading 状态 / 错误处理 |
| 4.3 | UI 细节打磨（配色、间距、动画） |
| 4.4 | 集成联调测试 |

---

## 附录

### A. 配色方案

| 节点类型 | 颜色 | 色值 |
|---------|------|------|
| Disease | 珊瑚红 | `#FF6B6B` |
| Symptom | 青绿 | `#4ECDC4` |
| Drug | 蓝紫 | `#6C5CE7` |
| BodyPart | 橙黄 | `#FECA57` |
| SideEffect | 灰蓝 | `#A29BFE` |

### B. 现有接口参考

当前 `test_graphrag.py` 的核心逻辑将被迁移到 `QueryService`：
- `graph.schema` 提取 → `QueryService.get_schema_for_prompt()`
- `GraphCypherQAChain` → `QueryService.ask()` 中编排
- 自定义 `CYPHER_GENERATION_TEMPLATE` → 配置化管理

### C. 技术风险与应对

| 风险 | 应对 |
|------|------|
| Neo4j 数据量大导致图谱卡顿 | 首次只加载概要节点（按类型聚合），按需展开 |
| LLM API 不稳定 | 加超时重试 + 错误提示 + 降级为纯 Cypher 查询 |
| vis-network 性能在大图上 | 设置 `node_limit=200`，超过时提示筛选 |
| 后端与前端跨域 | FastAPI CORSMiddleware 已支持 |
