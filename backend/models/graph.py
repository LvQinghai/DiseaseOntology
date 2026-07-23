"""图谱可视化相关 Pydantic 模型."""

from pydantic import BaseModel


class GraphNode(BaseModel):
    """图谱节点"""
    id: str
    label: str          # 显示名称 (name 属性)
    type: str           # 节点标签 (Disease/Symptom/...)
    color: str          # 显示颜色
    size: int = 10      # 节点大小


class GraphEdge(BaseModel):
    """图谱边"""
    id: str
    source: str         # 源节点 element_id
    target: str         # 目标节点 element_id
    type: str           # 关系类型
    label: str          # 显示标签（中文）


class GraphMeta(BaseModel):
    """图谱元信息"""
    total_nodes: int
    total_edges: int


class GraphData(BaseModel):
    """图谱完整数据"""
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    meta: GraphMeta | None = None
