"""本体编辑相关 API 路由."""

from fastapi import APIRouter, Query

from backend.models.editor import (
    CreateEntityRequest,
    UpdateEntityRequest,
    EntityResponse,
    CreateRelationshipRequest,
    UpdateRelationshipRequest,
    RelationshipResponse,
    SetPropertiesRequest,
    AvailableLabelsResponse,
    AvailableRelationshipsResponse,
    NodeSearchResult,
    DeletionCheckResult,
    RelationshipInstanceSummary,
)

router = APIRouter(prefix="/api/editor", tags=["本体编辑"])


# ==================== 实体 CRUD ====================

@router.post("/entities", response_model=EntityResponse)
def create_entity(req: CreateEntityRequest) -> EntityResponse:
    """创建实体节点."""
    from backend.main import get_editor_service
    return get_editor_service().create_entity(req)


@router.get("/entities/{element_id}", response_model=EntityResponse)
def get_entity(element_id: str) -> EntityResponse:
    """获取实体详情."""
    from backend.main import get_editor_service
    return get_editor_service().get_entity(element_id)


@router.put("/entities/{element_id}", response_model=EntityResponse)
def update_entity(element_id: str, req: UpdateEntityRequest) -> EntityResponse:
    """更新实体节点（名称/标签/属性）."""
    from backend.main import get_editor_service
    return get_editor_service().update_entity(element_id, req)


@router.get("/entities/{element_id}/deletion-check", response_model=DeletionCheckResult)
def check_entity_deletion(element_id: str) -> DeletionCheckResult:
    """校验节点是否可删除（返回关联关系列表）."""
    from backend.main import get_editor_service
    return get_editor_service().check_entity_deletion(element_id)


@router.delete("/entities/{element_id}")
def delete_entity(element_id: str) -> dict:
    """删除实体节点（Neo4j 要求节点不能有关联关系）."""
    from backend.main import get_editor_service
    return get_editor_service().delete_entity(element_id)


# ==================== 属性操作 ====================

@router.post("/entities/{element_id}/properties", response_model=EntityResponse)
def set_properties(element_id: str, req: SetPropertiesRequest) -> EntityResponse:
    """批量设置节点属性（合并模式）."""
    from backend.main import get_editor_service
    return get_editor_service().set_properties(element_id, req.properties)


@router.delete("/entities/{element_id}/properties/{key}", response_model=EntityResponse)
def delete_property(element_id: str, key: str) -> EntityResponse:
    """删除节点指定属性."""
    from backend.main import get_editor_service
    return get_editor_service().delete_property(element_id, key)


# ==================== 关系 CRUD ====================

@router.post("/relationships", response_model=RelationshipResponse)
def create_relationship(req: CreateRelationshipRequest) -> RelationshipResponse:
    """创建节点间关系."""
    from backend.main import get_editor_service
    return get_editor_service().create_relationship(req)


@router.get("/relationships/{rel_id}", response_model=RelationshipResponse)
def get_relationship(rel_id: str) -> RelationshipResponse:
    """获取关系详情."""
    from backend.main import get_editor_service
    return get_editor_service().get_relationship(rel_id)


@router.put("/relationships/{rel_id}", response_model=RelationshipResponse)
def update_relationship(rel_id: str, req: UpdateRelationshipRequest) -> RelationshipResponse:
    """更新关系（支持修改源节点/目标节点/类型/属性）."""
    from backend.main import get_editor_service
    return get_editor_service().update_relationship(rel_id, req)


@router.delete("/relationships/{rel_id}")
def delete_relationship(rel_id: str) -> dict:
    """删除关系."""
    from backend.main import get_editor_service
    return get_editor_service().delete_relationship(rel_id)


# ==================== 元数据 ====================

@router.get("/labels", response_model=AvailableLabelsResponse)
def get_available_labels() -> AvailableLabelsResponse:
    """获取可用标签列表."""
    from backend.main import get_editor_service
    labels = get_editor_service().get_available_labels()
    return AvailableLabelsResponse(labels=labels)


@router.get("/relationship-types", response_model=AvailableRelationshipsResponse)
def get_available_relationship_types() -> AvailableRelationshipsResponse:
    """获取可用关系类型列表."""
    from backend.main import get_editor_service
    types = get_editor_service().get_available_relationship_types()
    return AvailableRelationshipsResponse(relationship_types=types)


@router.get("/nodes/search", response_model=list[NodeSearchResult])
def search_nodes(keyword: str = Query(default="", min_length=0, description="搜索关键词（为空时返回全部节点）")) -> list[NodeSearchResult]:
    """搜索节点（供关系编辑器选择目标）."""
    from backend.main import get_editor_service
    return get_editor_service().search_nodes(keyword)


@router.get("/relationship-instances", response_model=list[RelationshipInstanceSummary])
def get_relationship_instances(
    type: str = Query(..., description="关系类型名称（如 TREATS）"),
) -> list[RelationshipInstanceSummary]:
    """获取指定关系类型的所有实例（源→目标对列表）"""
    from backend.main import get_editor_service
    return get_editor_service().get_relationship_instances(type)
