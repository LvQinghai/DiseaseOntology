"""本体编辑器 API 路由 —— v3.0: system_id → prefix 解析."""

from fastapi import APIRouter, HTTPException, Query

from backend.models.editor import (
    CreateEntityRequest,
    UpdateEntityRequest,
    EntityResponse,
    CreateRelationshipRequest,
    UpdateRelationshipRequest,
    RelationshipResponse,
    DeletionCheckResult,
    NodeSearchResult,
    RelationshipInstanceSummary,
)
from backend.repositories.neo4j_repository import Neo4jRepository

router = APIRouter(prefix="/api/editor", tags=["编辑器"])


def _resolve_prefix(system_id: str) -> str:
    """system_id → prefix 解析."""
    from backend.main import get_system_service
    try:
        return get_system_service().get_prefix(system_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


def _get_editor_service():
    from backend.main import get_editor_service
    return get_editor_service()


# ═══════════════════════════════════════════
# 实体 CRUD
# ═══════════════════════════════════════════

@router.post("/entities", response_model=EntityResponse)
def create_entity(
    req: CreateEntityRequest,
    system_id: str = Query(default="disease_ontology", description="系统标识"),
):
    """创建实体节点。"""
    prefix = _resolve_prefix(system_id)
    return _get_editor_service().create_entity(req, prefix)


@router.get("/entities/{element_id}", response_model=EntityResponse)
def get_entity(element_id: str):
    """获取实体详情。"""
    return _get_editor_service().get_entity(element_id)


@router.put("/entities/{element_id}", response_model=EntityResponse)
def update_entity(
    element_id: str,
    req: UpdateEntityRequest,
    system_id: str = Query(default="disease_ontology", description="系统标识"),
):
    """更新实体节点。"""
    prefix = _resolve_prefix(system_id)
    return _get_editor_service().update_entity(element_id, req, prefix)


@router.delete("/entities/{element_id}")
def delete_entity(
    element_id: str,
    force: bool = Query(default=False, description="级联删除关联关系"),
    system_id: str = Query(default="disease_ontology", description="系统标识"),
):
    """删除实体节点。force=true 时级联删除所有关联关系后再删除节点。"""
    prefix = _resolve_prefix(system_id)
    return _get_editor_service().delete_entity(element_id, force=force, prefix=prefix)


# ═══════════════════════════════════════════
# 属性操作
# ═══════════════════════════════════════════

@router.put("/entities/{element_id}/properties", response_model=EntityResponse)
def set_properties(element_id: str, properties: dict):
    """设置节点属性（合并模式）。"""
    return _get_editor_service().set_properties(element_id, properties)


@router.delete("/entities/{element_id}/properties/{key}", response_model=EntityResponse)
def remove_property(element_id: str, key: str):
    """删除节点属性。"""
    return _get_editor_service().delete_property(element_id, key)


# ═══════════════════════════════════════════
# 删除前检查
# ═══════════════════════════════════════════

@router.get("/entities/{element_id}/deletion-check", response_model=DeletionCheckResult)
def check_deletion(element_id: str):
    """检查节点是否可删除，返回关联关系列表。"""
    return _get_editor_service().check_entity_deletion(element_id)


# ═══════════════════════════════════════════
# 关系 CRUD
# ═══════════════════════════════════════════

@router.post("/relationships", response_model=RelationshipResponse)
def create_relationship(
    req: CreateRelationshipRequest,
    system_id: str = Query(default="disease_ontology", description="系统标识"),
):
    """创建节点间关系。"""
    prefix = _resolve_prefix(system_id)
    return _get_editor_service().create_relationship(req, prefix)


@router.get("/relationships/{rel_element_id}", response_model=RelationshipResponse)
def get_relationship(rel_element_id: str):
    """获取关系详情。"""
    return _get_editor_service().get_relationship(rel_element_id)


@router.put("/relationships/{rel_element_id}", response_model=RelationshipResponse)
def update_relationship(rel_element_id: str, req: UpdateRelationshipRequest):
    """更新关系。"""
    return _get_editor_service().update_relationship(rel_element_id, req)


@router.delete("/relationships/{rel_element_id}")
def delete_relationship(
    rel_element_id: str,
    system_id: str = Query(default="disease_ontology", description="系统标识"),
):
    """删除关系，并同步清理 SQLite 中该类型的语义定义（当该类型无剩余实例时）。"""
    prefix = _resolve_prefix(system_id)
    return _get_editor_service().delete_relationship(rel_element_id, prefix)


# ═══════════════════════════════════════════
# 元数据
# ═══════════════════════════════════════════

@router.get("/labels")
def get_available_labels(
    system_id: str = Query(default="disease_ontology", description="系统标识"),
):
    """获取可用标签列表（完整标签名，含前缀）。"""
    prefix = _resolve_prefix(system_id)
    return {"labels": _get_editor_service().get_available_labels(prefix)}


@router.get("/relationship-types")
def get_relationship_type_names(
    system_id: str = Query(default="disease_ontology", description="系统标识"),
):
    """获取可用关系类型列表（完整类型名，含前缀）。"""
    prefix = _resolve_prefix(system_id)
    return {
        "relationship_types": _get_editor_service().get_available_relationship_types(prefix),
    }


# ═══════════════════════════════════════════
# 搜索
# ═══════════════════════════════════════════

@router.get("/search-nodes", response_model=list[NodeSearchResult])
def search_nodes(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    system_id: str = Query(default="disease_ontology", description="系统标识"),
):
    """搜索节点（用于编辑器内选择源/目标节点）。"""
    prefix = _resolve_prefix(system_id)
    return _get_editor_service().search_nodes(keyword, prefix)


# ═══════════════════════════════════════════
# 关系实例
# ═══════════════════════════════════════════

@router.get("/relationship-instances/{rel_type}",
            response_model=list[RelationshipInstanceSummary])
def get_relationship_instances(
    rel_type: str,
    system_id: str = Query(default="disease_ontology", description="系统标识"),
):
    """获取指定关系类型的所有实例。"""
    prefix = _resolve_prefix(system_id)
    return _get_editor_service().get_relationship_instances(rel_type, prefix, limit=200)


@router.get("/relationships/duplicate-check")
def check_relationship_duplicate(
    source_id: str = Query(..., description="源节点 elementId"),
    target_id: str = Query(..., description="目标节点 elementId"),
    rel_type: str = Query(..., description="关系类型（短名，不含前缀）"),
    system_id: str = Query(default="disease_ontology"),
    exclude_id: str = Query(default="", description="排除的关系 elementId（编辑时）"),
):
    """检查指定源-目标-类型组合是否已存在关系。"""
    prefix = _resolve_prefix(system_id)
    full_type = f"{prefix}{rel_type}"
    results = Neo4jRepository.get_instance().execute_query(
        f"MATCH (a)-[r:`{full_type}`]->(b) "
        "WHERE elementId(a) = $source_id AND elementId(b) = $target_id "
        "AND elementId(r) <> $exclude_id "
        "RETURN count(r) AS cnt",
        {"source_id": source_id, "target_id": target_id, "exclude_id": exclude_id},
    )
    cnt = results[0].get("cnt", 0) if results else 0
    return {"exists": cnt > 0}
