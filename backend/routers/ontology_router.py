"""本体浏览相关 API 路由."""

from fastapi import APIRouter, HTTPException, Query
from backend.models.ontology import OntologyTree, NodeDetail, NodeInstance, RelationshipCatalogItem, SearchResult

router = APIRouter(prefix="/api/ontology", tags=["本体浏览"])


@router.get("/tree", response_model=OntologyTree)
def get_tree() -> OntologyTree:
    """获取完整本体树结构."""
    from backend.main import get_ontology_service
    return get_ontology_service().get_tree()


@router.get("/nodes/{element_id}", response_model=NodeDetail)
def get_node_detail(element_id: str) -> NodeDetail:
    """获取节点完整详情."""
    from backend.main import get_ontology_service
    svc = get_ontology_service()
    result = svc.get_node_detail(element_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"节点 {element_id} 不存在")
    return result


@router.get("/nodes/{element_id}/subclasses", response_model=list[NodeInstance])
def get_subclass_children(element_id: str) -> list[NodeInstance]:
    """获取节点的 SUB_CLASS_OF 子类（懒加载层级）."""
    from backend.main import get_ontology_service
    return get_ontology_service().get_subclass_children(element_id)


@router.get("/relationships", response_model=list[RelationshipCatalogItem])
def get_relationship_catalog() -> list[RelationshipCatalogItem]:
    """获取关系类型目录."""
    from backend.main import get_ontology_service
    svc = get_ontology_service()
    return svc.get_relationship_catalog()


@router.get("/search", response_model=list[SearchResult])
def search_nodes(keyword: str = Query(..., min_length=1, description="搜索关键词")):
    """全局模糊搜索节点."""
    from backend.main import get_ontology_service
    svc = get_ontology_service()
    return svc.search(keyword)
