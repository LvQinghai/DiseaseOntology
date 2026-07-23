"""图谱可视化相关 API 路由."""

from fastapi import APIRouter, HTTPException, Query
from backend.models.graph import GraphData

router = APIRouter(prefix="/api/graph", tags=["图谱可视化"])


@router.get("/overview", response_model=GraphData)
def get_overview():
    """获取全量图谱数据."""
    from backend.main import get_graph_service
    svc = get_graph_service()
    return svc.get_overview()


@router.get("/neighbors/{element_id}", response_model=GraphData)
def get_neighborhood(
    element_id: str,
    depth: int = Query(1, ge=1, le=3, description="邻居深度（1-3）"),
):
    """获取节点邻域子图."""
    from backend.main import get_graph_service
    svc = get_graph_service()
    result = svc.get_neighborhood(element_id, depth)
    if not result.nodes:
        raise HTTPException(status_code=404, detail=f"节点 {element_id} 不存在或无邻居")
    return result


@router.get("/path", response_model=GraphData)
def get_path(
    source: str = Query(..., description="起始节点 elementId"),
    target: str = Query(..., description="目标节点 elementId"),
):
    """获取两节点间的最短路径."""
    from backend.main import get_graph_service
    svc = get_graph_service()
    result = svc.get_path(source, target)
    if not result:
        raise HTTPException(status_code=404, detail="未找到路径")
    return result
