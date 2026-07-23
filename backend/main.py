"""FastAPI 应用入口 —— 疾病本体可视化系统后端."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.repositories.neo4j_repository import Neo4jRepository
from backend.services.ontology_service import OntologyService
from backend.services.graph_service import GraphService
from backend.services.query_service import QueryService

# ---- 全局服务实例 ----
_repo: Neo4jRepository | None = None
_ontology_svc: OntologyService | None = None
_graph_svc: GraphService | None = None
_query_svc: QueryService | None = None


def get_ontology_service() -> OntologyService:
    assert _ontology_svc is not None, "OntologyService 未初始化"
    return _ontology_svc


def get_graph_service() -> GraphService:
    assert _graph_svc is not None, "GraphService 未初始化"
    return _graph_svc


def get_query_service() -> QueryService:
    assert _query_svc is not None, "QueryService 未初始化"
    return _query_svc


# ---- 生命周期 ----
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _repo, _ontology_svc, _graph_svc, _query_svc
    print(f"🚀 正在连接 Neo4j: {settings.neo4j_uri}")
    _repo = Neo4jRepository(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
    )
    _ontology_svc = OntologyService(_repo)
    _graph_svc = GraphService(_repo)
    _query_svc = QueryService(_repo)
    print("✅ 服务初始化完成")
    yield
    if _repo:
        _repo.close()
        print("🔌 Neo4j 连接已关闭")


# ---- 应用 ----
app = FastAPI(
    title="疾病本体知识图谱可视化系统",
    description="基于 Neo4j 的疾病本体浏览、图谱可视化与 GraphRAG 智能问答",
    version="1.0.0",
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
from backend.routers import ontology_router, graph_router, query_router

app.include_router(ontology_router)
app.include_router(graph_router)
app.include_router(query_router)


@app.get("/")
def root():
    return {"service": "疾病本体知识图谱可视化系统", "version": "1.0.0", "status": "running"}


@app.get("/api/health")
def health():
    return {"status": "ok", "neo4j": "connected"}
