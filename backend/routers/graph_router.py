"""图谱可视化 API 路由 —— v3.0: system_id → prefix 解析."""

from fastapi import APIRouter, HTTPException, Query

from backend.models.graph import GraphData

router = APIRouter(prefix="/api/graph", tags=["图谱可视化"])


def _resolve_prefix(system_id: str) -> str:
    """system_id → prefix 解析."""
    from backend.main import get_system_service
    try:
        return get_system_service().get_prefix(system_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


def _get_graph_service():
    from backend.main import get_graph_service
    return get_graph_service()


# ───────────── 全量图谱 ─────────────

@router.get("/overview", response_model=GraphData)
def get_overview(
    system_id: str = Query(default="disease_ontology",
                           description="系统标识"),
):
    """获取全量图谱数据。"""
    prefix = _resolve_prefix(system_id)
    return _get_graph_service().get_overview(prefix)


# ───────────── 邻域展开 ─────────────

@router.get("/neighborhood/{element_id}", response_model=GraphData)
def get_neighborhood(element_id: str, depth: int = 1):
    """获取节点 N 跳邻域子图。"""
    result = _get_graph_service().get_neighborhood(element_id, depth)
    return result


# ───────────── 路径查找 ─────────────

@router.get("/path", response_model=GraphData)
def find_path(
    source_id: str = Query(..., description="起始节点 elementId"),
    target_id: str = Query(..., description="目标节点 elementId"),
):
    """查找两节点间的最短路径。"""
    result = _get_graph_service().get_path(source_id, target_id)
    if not result:
        raise HTTPException(status_code=404, detail="未找到路径")
    return result
