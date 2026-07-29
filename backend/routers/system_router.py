"""系统管理 API 路由 —— v3.0: SQLite 元数据 + Neo4j 清理 + v3.6: 关系语义."""

from fastapi import APIRouter, HTTPException, Query, Path

from backend.models.system import (
    SystemInfo,
    CreateSystemRequest,
    RelationSemanticInfo,
    UpsertRelationSemanticRequest,
    SystemSemanticsResponse,
)

router = APIRouter(prefix="/api/system", tags=["系统管理"])


def _get_system_service():
    """延迟导入以避免循环依赖."""
    from backend.main import get_system_service
    return get_system_service()


def _get_repo():
    """延迟导入 Neo4j Repository."""
    from backend.main import get_repository
    return get_repository()


def _invalidate_query_caches(prefix: str):
    """v3.8: 语义/数据变更后主动失效 QueryService 的缓存。"""
    try:
        from backend.main import get_query_service
        qs = get_query_service()
        if qs:
            qs.invalidate_semantics_cache(prefix)
    except Exception:
        pass  # 缓存失效失败不阻塞主流程


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


@router.get("/{system_id}/stats")
async def get_system_stats(system_id: str):
    """获取指定系统的详细统计信息（节点标签、关系类型及数量），用于删除前确认。"""
    svc = _get_system_service()
    system = svc.get_system(system_id)
    if not system:
        raise HTTPException(status_code=404, detail=f"系统 '{system_id}' 不存在")

    repo = _get_repo()
    stats = repo.get_system_stats(system.prefix)

    # 获取关系语义配置数量
    semantics_count = 0
    try:
        semantics = svc.get_relation_semantics(system.prefix)
        semantics_count = len(semantics)
    except Exception:
        pass

    return {
        "system_id": system.system_id,
        "name": system.name,
        "prefix": system.prefix,
        "node_count": stats["node_count"],
        "relationship_count": stats["relationship_count"],
        "node_labels": stats["node_labels"],
        "relationship_types": stats["relationship_types"],
        "semantics_count": semantics_count,
    }


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

    # v3.6: 清理该系统的关系语义配置
    deleted_semantics = 0
    try:
        semantics = svc.get_relation_semantics(system.prefix)
        deleted_semantics = len(semantics)
        for s in semantics:
            svc.delete_relation_semantic(system.prefix, s.rel_type)
    except Exception:
        pass  # 语义清理失败不阻塞删除操作

    # 删除 SQLite 记录
    svc.delete_system(system_id)

    return {
        "success": True,
        "message": f"系统 '{system.name}' ({system_id}) 已删除",
        "deleted_nodes": neo4j_cleaned.get("deleted_nodes", 0),
        "deleted_relationships": neo4j_cleaned.get("deleted_relationships", 0),
        "deleted_semantics": deleted_semantics,
    }


# ═══════════════════════════════════════════
# v3.6: 关系语义 CRUD 端点
# ═══════════════════════════════════════════

@router.get(
    "/{prefix}/relation-semantics",
    response_model=SystemSemanticsResponse,
)
async def get_relation_semantics(
    prefix: str = Path(..., description="系统前缀，如 MED_"),
):
    """获取指定系统的全部关系语义配置。"""
    svc = _get_system_service()
    return svc.get_semantics_for_query(prefix)


@router.put(
    "/{prefix}/relation-semantics/{rel_type}",
    response_model=RelationSemanticInfo,
)
async def upsert_relation_semantic(
    req: UpsertRelationSemanticRequest,
    prefix: str = Path(..., description="系统前缀"),
    rel_type: str = Path(..., description="关系类型原名"),
):
    """创建或更新一条关系语义。"""
    if req.rel_type and req.rel_type != rel_type:
        raise HTTPException(status_code=400, detail="URL 中的 rel_type 与请求体不一致")
    req.rel_type = rel_type
    svc = _get_system_service()
    result = svc.upsert_relation_semantic(prefix, req)
    _invalidate_query_caches(prefix)
    return result


@router.delete(
    "/{prefix}/relation-semantics/{rel_type}",
)
async def delete_relation_semantic(
    prefix: str = Path(..., description="系统前缀"),
    rel_type: str = Path(..., description="关系类型原名"),
):
    """删除一条关系语义。"""
    svc = _get_system_service()
    ok = svc.delete_relation_semantic(prefix, rel_type)
    if not ok:
        raise HTTPException(status_code=404, detail=f"语义'{rel_type}'不存在")
    _invalidate_query_caches(prefix)
    return {"success": True, "message": f"语义'{rel_type}'已删除"}


@router.post(
    "/{prefix}/relation-semantics/init",
)
async def init_relation_semantics(
    prefix: str = Path(..., description="系统前缀"),
):
    """从 Neo4j 自动扫描并初始化关系语义（不覆盖已有配置）。"""
    repo = _get_repo()
    rel_types = repo.get_relation_types_by_prefix(prefix)
    if not rel_types:
        raise HTTPException(
            status_code=404,
            detail=f"前缀 '{prefix}' 下未找到任何关系，请先导入或创建数据",
        )
    svc = _get_system_service()
    count = svc.init_semantics_from_neo4j(prefix, rel_types)
    _invalidate_query_caches(prefix)
    return {
        "success": True,
        "message": f"已初始化 {count} 条关系语义（共 {len(rel_types)} 种关系类型）",
        "initialized_count": count,
        "total_types": len(rel_types),
    }
