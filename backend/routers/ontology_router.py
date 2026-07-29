"""本体浏览 API 路由 —— v3.0: system_id → prefix 解析."""

from fastapi import APIRouter, HTTPException, Query

from backend.models.ontology import OntologyTree, NodeDetail, NodeInstance, \
    RelationshipCatalogItem, SearchResult

router = APIRouter(prefix="/api/ontology", tags=["本体浏览"])


def _resolve_prefix(system_id: str) -> str:
    """system_id → prefix 解析."""
    from backend.main import get_system_service
    try:
        return get_system_service().get_prefix(system_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


def _get_ontology_service():
    from backend.main import get_ontology_service
    return get_ontology_service()


# ───────────── 本体树 ─────────────

@router.get("/tree", response_model=OntologyTree)
def get_tree(
    system_id: str = Query(default="disease_ontology",
                           description="系统标识"),
):
    """获取完整本体树。"""
    prefix = _resolve_prefix(system_id)
    return _get_ontology_service().get_tree(prefix)


# ───────────── 节点详情 ─────────────

@router.get("/nodes/{element_id}", response_model=NodeDetail)
def get_node_detail(
    element_id: str,
    system_id: str = Query(default="disease_ontology", description="系统标识"),
):
    """获取节点完整详情。"""
    prefix = _resolve_prefix(system_id)
    result = _get_ontology_service().get_node_detail(element_id, prefix)
    if not result:
        raise HTTPException(status_code=404, detail=f"节点 {element_id} 不存在")
    return result


# ───────────── 子类展开 ─────────────

@router.get("/nodes/{element_id}/subclasses", response_model=list[NodeInstance])
def get_subclass_children(
    element_id: str,
    system_id: str = Query(default="disease_ontology", description="系统标识"),
):
    """获取节点的 SUB_CLASS_OF 子类。"""
    prefix = _resolve_prefix(system_id)
    return _get_ontology_service().get_subclass_children(element_id, prefix)


# ───────────── 关系目录 ─────────────

@router.get("/relationships", response_model=list[RelationshipCatalogItem])
def get_relationship_catalog(
    system_id: str = Query(default="disease_ontology", description="系统标识"),
):
    """获取关系类型目录（剥离前缀后）。"""
    prefix = _resolve_prefix(system_id)
    return _get_ontology_service().get_relationship_catalog(prefix)


# ───────────── 搜索 ─────────────

@router.get("/search", response_model=list[SearchResult])
def search(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    system_id: str = Query(default="disease_ontology", description="系统标识"),
):
    """全局模糊搜索。"""
    prefix = _resolve_prefix(system_id)
    return _get_ontology_service().search(keyword, prefix)
