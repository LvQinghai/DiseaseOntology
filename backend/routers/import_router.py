"""数据导入 API 路由."""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import StreamingResponse
import io

from backend.models.import_task import (
    DBConnection, TableInfo, ImportPreviewData, ImportResult,
    TableMapping, RelationshipMapping,
)


router = APIRouter(prefix="/api/import", tags=["数据导入"])


def _get_import_service():
    """延迟导入以避免循环依赖."""
    from backend.main import get_import_service
    return get_import_service()


# ─── Excel ───────────────────────────────────────

@router.post("/excel/preview")
async def preview_excel(file: UploadFile = File(...)) -> ImportPreviewData:
    """上传 Excel 并预览解析结果."""
    if not file.filename or not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "仅支持 .xlsx / .xls 格式")
    content = await file.read()
    return _get_import_service().preview_excel(content)


@router.post("/excel/import")
async def import_excel(
    file: UploadFile = File(...),
    system_name: str = Form(...),
    description: str = Form(""),
) -> ImportResult:
    """从 Excel 导入创建新系统."""
    if not file.filename or not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "仅支持 .xlsx / .xls 格式")
    content = await file.read()
    return _get_import_service().import_from_excel(content, system_name, description)


# ─── 关系数据库 ─────────────────────────────────

@router.post("/db/test")
async def test_connection(conn: DBConnection):
    """测试数据库连接."""
    ok = _get_import_service().test_connection(conn)
    return {"success": ok, "message": "连接成功" if ok else "连接失败"}


@router.post("/db/tables")
async def get_tables(conn: DBConnection) -> list[TableInfo]:
    """获取数据库所有表及列信息."""
    return _get_import_service().get_tables(conn)


@router.post("/db/preview")
async def preview_db(
    conn: DBConnection,
    entity_mappings: list[TableMapping],
    relationship_mappings: list[RelationshipMapping] | None = None,
) -> ImportPreviewData:
    """预览数据库导入数据."""
    return _get_import_service().preview_db(conn, entity_mappings, relationship_mappings)


@router.post("/db/import")
async def import_db(
    conn: DBConnection,
    entity_mappings: list[TableMapping],
    system_name: str,
    description: str = "",
    relationship_mappings: list[RelationshipMapping] | None = None,
) -> ImportResult:
    """从数据库导入创建新系统."""
    return _get_import_service().import_from_db(
        conn, entity_mappings, system_name, description, relationship_mappings
    )


# ─── 模板 ────────────────────────────────────────

@router.get("/template")
async def download_template():
    """下载 Excel 导入模板."""
    content = _get_import_service().generate_template()
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=import_template.xlsx"},
    )
