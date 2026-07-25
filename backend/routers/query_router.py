"""智能问答 API 路由 —— v3.0: system_id → prefix 解析."""

from fastapi import APIRouter, HTTPException

from backend.models.query import QueryRequest, QueryResult

router = APIRouter(prefix="/api/query", tags=["智能问答"])


def _resolve_prefix(system_id: str) -> str:
    """system_id → prefix 解析."""
    from backend.main import get_system_service
    try:
        return get_system_service().get_prefix(system_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


def _get_query_service():
    from backend.main import get_query_service
    return get_query_service()


@router.post("", response_model=QueryResult)
def ask_question(req: QueryRequest):
    """智能问答（GraphRAG + 规则引擎降级）。"""
    prefix = _resolve_prefix(req.system_id)
    return _get_query_service().ask(req.question, prefix)
