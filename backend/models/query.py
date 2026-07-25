"""智能问答相关 Pydantic 模型."""

from pydantic import BaseModel, ConfigDict


class QueryRequest(BaseModel):
    """问答请求"""
    question: str
    system_id: str = "disease_ontology"  # v3.0: 目标系统标识


class QueryResult(BaseModel):
    """问答结果"""
    model_config = ConfigDict(extra="ignore")
    answer: str
    cypher: str | None = None
    raw_data: list[dict] = []
