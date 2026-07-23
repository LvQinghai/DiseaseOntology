"""智能问答相关 API 路由."""

from fastapi import APIRouter
from backend.models.query import QueryRequest, QueryResult

router = APIRouter(prefix="/api/query", tags=["智能问答"])


@router.post("", response_model=QueryResult)
def ask_question(req: QueryRequest) -> QueryResult:
    """自然语言问答（GraphRAG）."""
    from backend.main import get_query_service
    svc = get_query_service()
    return svc.ask(req.question)


@router.get("/schema")
def get_schema():
    """获取当前图数据库 Schema 描述（供调试）."""
    from backend.main import get_query_service
    svc = get_query_service()
    return {"schema": svc.get_schema_text()}
