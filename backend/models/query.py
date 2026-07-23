"""智能问答相关 Pydantic 模型."""

from pydantic import BaseModel


class QueryRequest(BaseModel):
    """问答请求"""
    question: str


class QueryResult(BaseModel):
    """问答结果"""
    answer: str
    cypher: str | None = None
    raw_data: list[dict] = []
