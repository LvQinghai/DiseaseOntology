"""本体浏览相关 Pydantic 模型."""

from pydantic import BaseModel


class PropertyDetail(BaseModel):
    """节点属性定义（名称+示例值）"""
    name: str
    sample_value: str | None = None


class NodeTypeInfo(BaseModel):
    """节点类型元信息"""
    label: str
    count: int
    properties: list[PropertyDetail] = []
    instances: list["NodeInstance"] = []


class NodeInstance(BaseModel):
    """节点实例摘要（树展示用，不含完整属性）"""
    element_id: str
    name: str
    labels: list[str]
    child_count: int = 0  # SUB_CLASS_OF 子节点数量，0 表示无子类（叶节点）


class RelationshipItem(BaseModel):
    """节点的单条关系"""
    type: str
    direction: str  # "incoming" | "outgoing"
    target_element_id: str
    target_name: str
    target_label: str
    properties: dict = {}


class NodeDetail(BaseModel):
    """节点完整详情"""
    element_id: str
    labels: list[str]
    properties: dict
    incoming_relationships: list[RelationshipItem] = []
    outgoing_relationships: list[RelationshipItem] = []


class RelationshipCatalogItem(BaseModel):
    """关系类型目录条目"""
    type: str
    count: int
    source_labels: list[str]
    target_labels: list[str]
    description: str = ""


class OntologyTree(BaseModel):
    """完整本体树"""
    node_types: list[NodeTypeInfo]
    relationship_types: list[RelationshipCatalogItem]


class SearchResult(BaseModel):
    """搜索结果"""
    element_id: str
    name: str
    labels: list[str]
    match_field: str  # "name" | "property"
