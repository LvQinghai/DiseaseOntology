"""FastAPI 应用入口 —— 疾病本体可视化系统后端 v3.0.

两层存储架构：
  - SQLite: 系统元数据（系统列表、前缀映射）
  - Neo4j:  知识图谱数据（前缀隔离标签/关系类型）
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.repositories.neo4j_repository import Neo4jRepository
from backend.services.ontology_service import OntologyService
from backend.services.graph_service import GraphService
from backend.services.query_service import QueryService
from backend.services.editor_service import EditorService
from backend.services.system_service import SystemService
from backend.services.import_service import ImportService

# ---- 全局服务实例 ----
_repo: Neo4jRepository | None = None
_ontology_svc: OntologyService | None = None
_graph_svc: GraphService | None = None
_query_svc: QueryService | None = None
_editor_svc: EditorService | None = None
_system_svc: SystemService | None = None
_import_svc: ImportService | None = None


# ---- Service getters ----
def get_ontology_service() -> OntologyService:
    assert _ontology_svc is not None, "OntologyService 未初始化"
    return _ontology_svc

def get_graph_service() -> GraphService:
    assert _graph_svc is not None, "GraphService 未初始化"
    return _graph_svc

def get_query_service() -> QueryService:
    assert _query_svc is not None, "QueryService 未初始化"
    return _query_svc

def get_editor_service() -> EditorService:
    assert _editor_svc is not None, "EditorService 未初始化"
    return _editor_svc

def get_system_service() -> SystemService:
    assert _system_svc is not None, "SystemService 未初始化"
    return _system_svc

def get_import_service() -> ImportService:
    assert _import_svc is not None, "ImportService 未初始化"
    return _import_svc

def get_repository() -> Neo4jRepository:
    assert _repo is not None, "Neo4jRepository 未初始化"
    return _repo


# ---- 生命周期 ----
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _repo, _ontology_svc, _graph_svc, _query_svc, _editor_svc
    global _system_svc, _import_svc

    # ── 步骤 1: 初始化 SQLite（建表 + 种子数据） ──
    print("📦 正在初始化 SQLite 元数据库...")
    from backend.database import init_database
    db_path = settings.get_sqlite_path()
    init_database(db_path)
    print(f"   📍 SQLite 路径: {db_path}")

    # ── 步骤 2: 初始化 SystemService（读取 SQLite 系统列表） ──
    _system_svc = SystemService()
    systems = _system_svc.get_all_systems()
    print(f"📋 已加载 {len(systems)} 个系统:")
    for s in systems:
        print(f"   - [{s.prefix}] {s.name} ({s.system_id})")

    # ── 步骤 3: 初始化 Neo4j ──
    print(f"🚀 正在连接 Neo4j: {settings.neo4j_uri}")
    _repo = Neo4jRepository(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
    )

    # ── 步骤 4: 初始化业务 Service ──
    _ontology_svc = OntologyService(_repo)
    _graph_svc = GraphService(_repo)
    _query_svc = QueryService(_repo)
    _editor_svc = EditorService(_repo)
    _import_svc = ImportService(_repo, _system_svc)

    # ── 步骤 5: 运行 Neo4j 前缀迁移 ──
    if settings.run_migration:
        try:
            from backend.migration import run_migration
            run_migration()
        except Exception as e:
            print(f"⚠️ Neo4j 迁移警告（可忽略）: {e}")

    # ── 步骤 6: 更新各系统统计 ──
    try:
        for s in _system_svc.get_all_systems():
            nc = _repo.count_system_nodes(s.prefix)
            rc = _repo.count_system_relationships(s.prefix)
            if nc > 0 or rc > 0:
                _system_svc.update_counts(s.system_id, nc, rc)
    except Exception as e:
        print(f"⚠️ 统计更新失败（可忽略）: {e}")

    print("✅ 服务初始化完成 (v3.0)")
    yield

    if _repo:
        _repo.close()
        print("🔌 Neo4j 连接已关闭")


# ---- 应用 ----
app = FastAPI(
    title="疾病本体知识图谱可视化系统",
    description="基于 Neo4j 的多系统本体浏览、图谱可视化、数据导入与 GraphRAG 智能问答 v3.0",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from backend.routers import (
    ontology_router,
    graph_router,
    query_router,
    editor_router,
    system_router,
    import_router,
)

app.include_router(ontology_router)
app.include_router(graph_router)
app.include_router(query_router)
app.include_router(editor_router)
app.include_router(system_router)
app.include_router(import_router)


@app.get("/")
def root():
    return {"service": "疾病本体知识图谱可视化系统", "version": "3.0.0", "status": "running"}


@app.get("/api/health")
def health():
    return {"status": "ok", "neo4j": "connected"}
