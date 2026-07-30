# DiseaseOntology

基于 **FastAPI + Vue 3 + Neo4j + SQLite** 构建的疾病本体知识图谱可视化与智能问答系统。

项目支持多套知识图谱系统隔离管理、Neo4j 图谱浏览、关系型数据库与 Excel 数据导入、实体关系编辑、图谱可视化，以及基于 GraphRAG 的自然语言问答。

## 功能特性

- 多系统知识图谱管理
- 基于 Neo4j 的实体、关系和本体树浏览
- 交互式知识图谱可视化
- Excel 实体/关系数据导入
- 关系型数据库导入
  - 数据库连接测试
  - 表和字段发现
  - 实体、关系字段映射
  - 业务 Label 映射
  - 数据预览与验证
  - Cypher 预览
  - 批量执行与结果校验
  - 失败快照恢复和 SQLite 临时记录清理
- 实体和关系在线编辑
- 系统前缀隔离，支持多套图谱共存
- 图谱节点按实体 Label 动态配色
- GraphRAG 智能问答
- FastAPI 自动接口文档

## 技术栈

| 模块 | 技术 |
|---|---|
| 后端 | Python 3.10+、FastAPI、Uvicorn、Pydantic |
| 前端 | Vue 3、TypeScript、Vite、Ant Design Vue、Pinia |
| 图数据库 | Neo4j 5.x |
| 系统元数据 | SQLite、SQLAlchemy |
| 图谱可视化 | vis-network、vis-data |
| 数据导入 | openpyxl、SQLAlchemy 数据库连接 |
| 智能问答 | OpenAI 兼容 LLM API、GraphRAG |

## 系统架构

```text
┌──────────────────────┐
│ Vue 3 前端            │
│ Vite + Ant Design Vue │
└──────────┬───────────┘
           │ HTTP / REST API
┌──────────▼───────────┐
│ FastAPI 后端          │
│ Router / Service      │
│ Import / GraphRAG     │
└───────┬───────┬───────┘
        │       │
┌───────▼───┐ ┌─▼────────────┐
│ SQLite    │ │ Neo4j        │
│ 系统元数据 │ │ 知识图谱数据 │
└───────────┘ └──────────────┘
```

SQLite 保存系统名称、描述、前缀和统计信息；Neo4j 保存实体、关系和图谱数据。不同系统通过唯一前缀隔离，例如 `MED_`、`ORG_`。

## 环境要求

- Python 3.10 或更高版本
- Node.js 18 或更高版本
- npm 9 或更高版本
- Neo4j 5.x
- Git

建议使用以下端口：

| 服务 | 默认地址 |
|---|---|
| Neo4j Bolt | `bolt://localhost:7687` |
| Neo4j Browser | `http://localhost:7474` |
| FastAPI | `http://localhost:8080` |
| Vue 开发服务器 | `http://localhost:3000` |

## 获取项目

```bash
git clone https://github.com/<your-account>/DiseaseOntology.git
cd DiseaseOntology
```

## 配置 Neo4j

1. 安装并启动 Neo4j 5.x。
2. 创建或确认 Neo4j 用户名和密码。
3. 确认 Bolt 服务监听在 `7687` 端口。
4. 首次启动项目时，后端会自动初始化 SQLite 元数据库：

```text
backend/data/systems.db
```

Neo4j Community Edition 不要求为每套图谱创建独立数据库，项目使用节点 Label 和关系类型前缀实现系统隔离。

## 后端安装与启动

在项目根目录执行：

### 1. 创建虚拟环境

macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

如果需要从其他关系型数据库导入数据，根据实际数据库安装对应驱动：

```bash
# MySQL
pip install pymysql

# PostgreSQL
pip install psycopg2-binary

# SQL Server
pip install pyodbc
```

### 3. 创建环境变量文件

在项目根目录创建 `.env` 文件。不要把真实密码、API Key 或其他敏感信息提交到 GitHub：

```env
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=请替换为你的Neo4j密码

# SQLite 元数据库，可选；为空时使用 backend/data/systems.db
SQLITE_PATH=

# 服务
HOST=0.0.0.0
PORT=8080

# GraphRAG LLM，可选
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY=请替换为你的API密钥
LLM_MODEL=你的模型名称
```

如果不使用智能问答，可以暂时不配置 LLM；图谱浏览、数据导入和实体关系管理仍可使用。

### 4. 启动后端

```bash
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8080
```

后端启动后访问：

- 健康检查：<http://localhost:8080/api/health>
- Swagger API 文档：<http://localhost:8080/docs>
- ReDoc 文档：<http://localhost:8080/redoc>

健康检查返回 `status: ok` 且 Neo4j 连接正常后，再启动前端。

## 前端安装与启动

打开新的终端窗口，在项目根目录执行：

```bash
cd frontend
npm install
npm run dev
```

浏览器访问：

<http://localhost:3000>

前端开发服务器会将 `/api` 请求代理到 `http://localhost:8080`。如果修改了后端端口，请同步修改 `frontend/vite.config.ts` 中的代理地址。

## 生产构建

```bash
cd frontend
npm run build
```

构建产物位于：

```text
frontend/dist/
```

预览生产构建：

```bash
npm run preview
```

生产环境建议使用 Nginx 或其他 Web 服务器托管 `frontend/dist`，并将 `/api` 反向代理到 FastAPI 服务。

## 快速使用

### 1. 浏览默认疾病知识图谱

1. 启动 Neo4j、后端和前端。
2. 打开 <http://localhost:3000>。
3. 在左上角系统下拉框选择知识图谱系统。
4. 在左侧本体树中选择实体类型或实例。
5. 在右侧查看节点关系和邻居图谱。
6. 使用搜索、路径查询或详情面板查看数据。

### 2. 创建新的知识图谱系统

1. 进入系统管理功能。
2. 填写系统名称、描述和前缀。
3. 前缀建议使用大写字母和下划线，例如：

```text
ORG_
MED_
CAR_
```

4. 保存后切换到新系统。
5. 通过 Excel 或关系型数据库导入数据。

系统前缀会自动标准化；三位大写前缀会自动补充下划线。

### 3. 导入 Excel 数据

1. 进入“导入数据”。
2. 选择 Excel 文件。
3. 检查实体 Sheet 和关系 Sheet 的识别结果。
4. 查看数据预览和验证报告。
5. 预览 Cypher 语句。
6. 确认执行导入。
7. 在结果页检查实体数量、关系数量和警告信息。

### 4. 导入关系型数据库

关系型数据库导入流程如下：

```text
连接数据库
  → 发现表和字段
  → 配置实体/关系映射
  → 读取数据并预览
  → 数据验证
  → 生成 Cypher
  → 确认执行
  → 结果校验
  → 失败时恢复快照
```

实体映射中的业务标签字段必须正确配置为 `label_column` 或统一 `target_label`。预览结果应类似：

```json
{
  "label": "员工",
  "name": "张三",
  "部门": "技术部"
}
```

其中 `label` 会生成 Neo4j 节点 Label，例如：

```cypher
CREATE (n:`ORG_员工`)
```

Label 字段不会重复保存为普通属性。如果预览阶段缺少有效 Label，系统会阻止导入并提示修正映射。

### 5. 使用 GraphRAG 问答

1. 在 `.env` 中配置 OpenAI 兼容的 LLM API。
2. 启动后端和前端。
3. 在问答页面输入自然语言问题，例如：

```text
某疾病有哪些常见症状？
某药物可能产生哪些副作用？
```

4. 系统会结合实体识别、图谱 Schema、语义信息和 Cypher 查询生成答案。

LLM 不可用时，部分查询功能可能无法使用，但普通图谱浏览和数据管理不受影响。

## 导入结果验证

导入组织员工绩效等新系统后，可以在 Neo4j Browser 中执行：

```cypher
MATCH (n)
WHERE any(label IN labels(n) WHERE label STARTS WITH 'ORG_')
RETURN labels(n), count(*)
ORDER BY count(*) DESC;
```

检查结果应包含真实业务 Label，例如：

```text
["ORG_员工"]
["ORG_部门"]
["ORG_岗位"]
```

而不应所有节点都显示为：

```text
["ORG_Entity"]
```

## 数据目录说明

```text
backend/data/
├── systems.db       # SQLite 系统元数据库
├── backups/         # Neo4j 导入前快照
└── baselines/       # 基线备份元数据
```

以下文件通常不应提交到公开仓库：

- `.env`
- 含真实业务数据的备份文件
- 本地 SQLite 数据库文件
- Neo4j 导出文件
- 日志、缓存和构建产物

如果项目中已经存在包含真实密码或 API Key 的 `.env`，请在上传 GitHub 前立即删除、加入 `.gitignore`，并更换已经暴露的凭据。

## 测试与检查

Python 代码编译检查：

```bash
python -m compileall -q backend
```

检查 Git 空白字符错误：

```bash
git diff --check
```

前端类型检查和生产构建：

```bash
cd frontend
npm run build
```

## 常见问题

### Neo4j 连接失败

检查以下配置：

- Neo4j 服务是否已启动；
- `NEO4J_URI` 是否为正确的 Bolt 地址；
- 用户名和密码是否正确；
- `7687` 端口是否可访问；
- 是否存在防火墙或 Docker 端口映射问题。

### 前端页面无法访问后端接口

确认：

1. 后端运行在 `8080` 端口；
2. 前端通过 `npm run dev` 启动在 `3000` 端口；
3. `frontend/vite.config.ts` 的 proxy target 指向后端地址；
4. 浏览器访问 <http://localhost:8080/api/health> 正常。

### 导入后所有节点都是 `Entity`

通常表示业务标签字段没有正确映射。请检查：

- `label_column` 是否指向真实的 Label 字段；
- 预览结果中的 `entities[].label` 是否为业务标签；
- 是否错误地把 Label 字段当成普通属性；
- Neo4j 中的实际节点 Label 是否以目标系统前缀开头。

### 导入失败后是否会产生脏数据

正式导入前会创建 Neo4j 快照。执行失败时，系统会尝试恢复快照；如果本次导入创建了新的系统记录，也会清理对应的 SQLite 临时记录。仍建议在生产环境导入前备份 Neo4j 和 SQLite 文件。

### LLM 问答不可用

检查：

- `LLM_API_BASE` 是否为 OpenAI 兼容接口地址；
- `LLM_API_KEY` 是否有效；
- `LLM_MODEL` 是否为服务端支持的模型；
- 网络是否可以访问 LLM 服务；
- 后端日志中是否存在超时或 SSL 错误。

## 安全建议

- 不要将 `.env`、数据库密码、API Key 和真实业务数据提交到 GitHub。
- 生产环境不要使用默认 Neo4j 密码。
- 使用最小权限的数据库账号进行关系型数据库读取。
- 对外部署时关闭或保护 Swagger 文档。
- 配置反向代理、HTTPS、身份认证和访问控制。
- 定期备份 `backend/data/systems.db` 和 Neo4j 数据。

## 项目文档

- [v4.5 设计文档](docs/v4.5-design.md)
- [GraphRAG 设计文档](docs/graphrag-design.md)
- [v3.0 设计文档](docs/v3.0-design.md)

## 许可证

当前仓库尚未声明开源许可证。如果计划公开发布，请根据项目实际授权方式添加 `LICENSE` 文件，例如 MIT、Apache-2.0 或 GPL-3.0。

## 贡献

欢迎通过 Issue 或 Pull Request 提交问题和改进建议。

提交代码前请确认：

1. 不包含密码、API Key 或真实业务数据；
2. 后端代码可以通过编译检查；
3. 前端可以完成生产构建；
4. 设计文档和接口变更已同步更新。
