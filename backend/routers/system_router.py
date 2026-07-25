"""系统管理 API 路由 —— v3.0: SQLite 元数据 + Neo4j 清理."""

from fastapi import APIRouter, HTTPException, Query

from backend.models.system import SystemInfo, CreateSystemRequest

router = APIRouter(prefix="/api/system", tags=["系统管理"])


def _get_system_service():
    """延迟导入以避免循环依赖."""
    from backend.main import get_system_service
    return get_system_service()


def _get_repo():
    """延迟导入 Neo4j Repository."""
    from backend.main import get_repository
    return get_repository()


# ───────────── 查询 ─────────────

@router.get("/list")
async def list_systems() -> list[SystemInfo]:
    """获取所有系统列表（从 SQLite）。"""
    return _get_system_service().get_all_systems()


@router.get("/default")
async def get_default() -> SystemInfo:
    """获取默认系统。"""
    from backend.config import settings
    svc = _get_system_service()
    system = svc.get_system(settings.DEFAULT_SYSTEM_ID)
    if not system:
        raise HTTPException(status_code=404, detail="默认系统不存在")
    return system


@router.get("/{system_id}")
async def get_system(system_id: str) -> SystemInfo:
    """获取指定系统详情。"""
    svc = _get_system_service()
    system = svc.get_system(system_id)
    if not system:
        raise HTTPException(status_code=404, detail=f"系统 '{system_id}' 不存在")
    return system


# ───────────── 写操作 ─────────────

@router.post("/create")
async def create_system(req: CreateSystemRequest) -> SystemInfo:
    """创建新系统（写入 SQLite）。"""
    try:
        return _get_system_service().create_system(
            name=req.name, description=req.description, prefix=req.prefix,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{system_id}")
async def delete_system(
    system_id: str,
    clean_neo4j: bool = Query(default=True,
                               description="是否同时清理 Neo4j 中的前缀数据"),
):
    """删除系统（SQLite 记录 + 可选清理 Neo4j 数据）。

    - clean_neo4j=True: 同时删除 Neo4j 中对应前缀的节点和关系。
    - 不可删除默认系统。
    """
    from backend.config import settings
    if system_id == settings.DEFAULT_SYSTEM_ID:
        raise HTTPException(
            status_code=400,
            detail=f"不允许删除默认系统 '{settings.DEFAULT_SYSTEM_NAME}'",
        )

    svc = _get_system_service()
    system = svc.get_system(system_id)
    if not system:
        raise HTTPException(status_code=404, detail=f"系统 '{system_id}' 不存在")

    # 清理 Neo4j 中的前缀数据
    neo4j_cleaned = {}
    if clean_neo4j:
        repo = _get_repo()
        neo4j_cleaned = repo.delete_system_data(system.prefix)

    # 删除 SQLite 记录
    svc.delete_system(system_id)

    return {
        "success": True,
        "message": f"系统 '{system.name}' ({system_id}) 已删除",
        "neo4j_deleted_nodes": neo4j_cleaned.get("deleted_nodes", 0),
        "neo4j_deleted_relationships": neo4j_cleaned.get("deleted_relationships", 0),
    }
