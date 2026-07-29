"""本体编辑相关 Pydantic 模型."""

from typing import Any
from pydantic import BaseModel


# ===== 实体 =====

class CreateEntityRequest(BaseModel):
    """创建实体请求"""
    label: str                                # 节点标签
    name: str                                 # 节点名称（必填）
    properties: dict[str, Any] = {}           # 其他属性


class UpdateEntityRequest(BaseModel):
    """更新实体请求"""
    name: str | None = None                   # 更新名称
    label: str | None = None                  # 更新标签
    properties: dict[str, Any] | None = None  # 合并更新属性（None 字段不变）


class EntityResponse(BaseModel):
    """实体响应"""
    element_id: str
    labels: list[str]
    name: str
    properties: dict
    relationship_count: int                   # 关联关系数


# ===== 关系 =====

class CreateRelationshipRequest(BaseModel):
    """创建关系请求"""
    source_element_id: str = ""               # 可选，填写时需与 target 共同提供且均为已存在节点
    target_element_id: str = ""               # 可选，填写时需与 source 共同提供且均为已存在节点
    type: str                                 # 关系类型
    properties: dict[str, Any] = {}


class UpdateRelationshipRequest(BaseModel):
    """更新关系请求"""
    properties: dict[str, Any] | None = None
    source_element_id: str | None = None
    target_element_id: str | None = None
    type: str | None = None


class RelationshipResponse(BaseModel):
    """关系响应"""
    element_id: str
    type: str
    source_id: str
    source_name: str
    target_id: str
    target_name: str
    properties: dict


# ===== 批量属性 =====

class SetPropertiesRequest(BaseModel):
    """批量设置属性"""
    properties: dict[str, Any]


# ===== 元数据 =====

class AvailableLabelsResponse(BaseModel):
    """可用标签列表"""
    labels: list[str]


class AvailableRelationshipsResponse(BaseModel):
    """可用关系类型列表"""
    relationship_types: list[str]


class NodeSearchResult(BaseModel):
    """节点搜索结果"""
    element_id: str
    name: str
    labels: list[str]


# ===== 删除校验 =====

class RelationshipBrief(BaseModel):
    """关系简要信息（删除校验用）"""
    element_id: str
    type: str
    direction: str                          # 'incoming' | 'outgoing'
    other_node_name: str
    other_node_element_id: str
    other_node_label: str


class DeletionCheckResult(BaseModel):
    """删除校验结果"""
    can_delete: bool
    name: str
    relationship_count: int
    relationships: list[RelationshipBrief]
    message: str


# ===== 关系实例列表（编辑器中展示） =====

class RelationshipInstanceSummary(BaseModel):
    """关系实例摘要（编辑器中展示所有源-目标对）"""
    element_id: str = ""
    source_id: str = ""
    source_name: str = ""
    source_label: str = ""
    target_id: str = ""
    target_name: str = ""
    target_label: str = ""
