"""数据导入 API 路由 (v3.5: 含验证/备份/回滚 + v3.6: 语义自动初始化)."""

import io
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Body
from fastapi.responses import StreamingResponse

from backend.models.import_task import (
    DBConnection, TableInfo, ImportPreviewData, ImportResult,
    TableMapping, RelationshipMapping,
)
from backend.services.system_service import normalize_prefix

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/import", tags=["数据导入"])


def _get_import_service():
    """延迟导入以避免循环依赖."""
    from backend.main import get_import_service
    return get_import_service()


def _get_repo():
    """获取 Neo4jRepository."""
    from backend.main import get_repository
    return get_repository()


def _get_tx_manager():
    """获取事务管理器 (v3.5)."""
    from backend.services.neo4j_tx_manager import Neo4jTransactionManager
    repo = _get_repo()
    return Neo4jTransactionManager(repo)


# ══════════════════════════════════════════════════
# v3.5 新增: Sheet 检测
# ══════════════════════════════════════════════════

@router.post("/excel/sheets")
async def detect_excel_sheets(file: UploadFile = File(...)):
    """★ v3.5: 检测 Excel 中各 Sheet 的类型（实体/关系/未知）。"""
    if not file.filename or not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "仅支持 .xlsx / .xls 格式")
    content = await file.read()
    from backend.services.excel_detector import ExcelSheetDetector
    detector = ExcelSheetDetector()
    result = detector.detect_sheets(content)
    return {
        "entity_sheet": result.entity_sheet.sheet_name if result.entity_sheet else None,
        "relationship_sheet": result.relationship_sheet.sheet_name if result.relationship_sheet else None,
        "sheets": result.all_sheets,
        "unmatched": result.unmatched_sheets,
        "errors": result.parse_errors,
    }


# ══════════════════════════════════════════════════
# v3.5 新增: 数据验证
# ══════════════════════════════════════════════════

@router.post("/excel/validate")
async def validate_excel(file: UploadFile = File(...)):
    """★ v3.5: 解析并完整验证 Excel 数据（新建模式）。"""
    if not file.filename or not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "仅支持 .xlsx / .xls 格式")
    content = await file.read()

    from backend.services.excel_detector import ExcelSheetDetector
    from backend.services.import_validator import ImportValidator

    detector = ExcelSheetDetector()
    parse_result = detector.detect_sheets(content)

    validator = ImportValidator()
    report = validator.validate(
        parse_result.entity_sheet,
        parse_result.relationship_sheet,
        mode="new",
    )
    # 填充未识别的 Sheet 列表到检测摘要
    report.detection_summary["unmatched_sheets"] = parse_result.unmatched_sheets

    # 附带预览数据
    preview_data = validator.get_preview(
        parse_result.entity_sheet,
        parse_result.relationship_sheet,
    )

    return {
        "is_valid": report.is_valid,
        "entity_count": report.entity_count,
        "relationship_count": report.relationship_count,
        "error_count": report.error_count,
        "warning_count": report.warning_count,
        "issues": [
            {
                "severity": i.severity.value,
                "code": i.code,
                "message": i.message,
                "sheet_type": i.sheet_type,
                "row_index": i.row_index,
                "field": i.field,
                "detail": i.detail,
            }
            for i in report.issues
        ],
        "preview": preview_data,
        "conflict_entities": [],
        "conflict_relationships": [],
        "detection_summary": report.detection_summary,
    }


@router.post("/excel/validate-append")
async def validate_excel_append(
    file: UploadFile = File(...),
    target_system_id: str = Form(...),
):
    """★ v3.5: 解析并验证 Excel 数据（追加模式，含冲突检测）。"""
    if not file.filename or not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "仅支持 .xlsx / .xls 格式")
    content = await file.read()

    # 获取目标系统的 prefix
    svc = _get_import_service()
    system = svc.system_service.get_system(target_system_id)
    if not system:
        raise HTTPException(404, f"系统 {target_system_id} 不存在")
    target_prefix = system.prefix

    from backend.services.excel_detector import ExcelSheetDetector
    from backend.services.import_validator import ImportValidator

    detector = ExcelSheetDetector()
    parse_result = detector.detect_sheets(content)

    repo = _get_repo()
    validator = ImportValidator(repo=repo)
    report = validator.validate(
        parse_result.entity_sheet,
        parse_result.relationship_sheet,
        mode="append",
        target_prefix=target_prefix,
    )
    report.detection_summary["unmatched_sheets"] = parse_result.unmatched_sheets

    preview_data = validator.get_preview(
        parse_result.entity_sheet,
        parse_result.relationship_sheet,
    )

    return {
        "is_valid": report.is_valid,
        "entity_count": report.entity_count,
        "relationship_count": report.relationship_count,
        "error_count": report.error_count,
        "warning_count": report.warning_count,
        "issues": [
            {
                "severity": i.severity.value,
                "code": i.code,
                "message": i.message,
                "sheet_type": i.sheet_type,
                "row_index": i.row_index,
                "field": i.field,
                "detail": i.detail,
            }
            for i in report.issues
        ],
        "preview": preview_data,
        "conflict_entities": report.conflict_entities,
        "conflict_relationships": report.conflict_relationships,
        "detection_summary": report.detection_summary,
    }


# ══════════════════════════════════════════════════
# v3.5 新增: Cypher 预览
# ══════════════════════════════════════════════════

@router.post("/excel/generate-cypher")
async def generate_cypher(
    file: UploadFile = File(...),
    prefix: str = Form(...),
    mode: str = Form("new"),       # "new" | "append"
):
    """★ v3.5: 生成 Cypher 预览语句（不写入 Neo4j）。"""
    if not file.filename or not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "仅支持 .xlsx / .xls 格式")
    content = await file.read()

    from backend.services.excel_detector import ExcelSheetDetector
    from backend.services.cypher_generator import CypherGenerator

    detector = ExcelSheetDetector()
    parse_result = detector.detect_sheets(content)

    # 标准化前缀（自动追加下划线）
    try:
        actual_prefix = normalize_prefix(prefix)
    except ValueError as e:
        raise HTTPException(400, str(e))

    strategy = "MERGE" if mode == "append" else "CREATE"
    generator = CypherGenerator(prefix=actual_prefix)
    batch = generator.generate(
        parse_result.entity_sheet,
        parse_result.relationship_sheet,
        strategy=strategy,
    )

    return {
        "entity_cypher": [
            {"statement": s.statement, "description": s.description}
            for s in batch.entity_statements
        ],
        "relationship_cypher": [
            {"statement": s.statement, "description": s.description}
            for s in batch.relationship_statements
        ],
        "total_entity_statements": len(batch.entity_statements),
        "total_relationship_statements": len(batch.relationship_statements),
        "total_operations": batch.total_operations,
    }


# ══════════════════════════════════════════════════
# v3.5 新增: 带备份的执行导入
# ══════════════════════════════════════════════════

@router.post("/excel/execute")
async def execute_excel_import(
    file: UploadFile = File(...),
    mode: str = Form(...),                    # "new" | "append"
    prefix: str = Form(""),
    system_name: str = Form(""),
    description: str = Form(""),
    target_system_id: str = Form(""),         # append 模式必填
    strategy: str = Form("CREATE"),           # 创建策略
):
    """★ v3.5: 带备份的完整导入流程（解析→验证→备份→写入→验证结果）。

    - mode="new": 创建新系统（prefix 自动标准化，追加下划线）
    - mode="append": 追加到已有系统
    """
    if not file.filename or not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "仅支持 .xlsx / .xls 格式")
    content = await file.read()

    from backend.services.excel_detector import ExcelSheetDetector
    from backend.services.import_validator import ImportValidator
    from backend.services.cypher_generator import CypherGenerator

    detector = ExcelSheetDetector()
    parse_result = detector.detect_sheets(content)

    # 确定实际使用的 prefix
    actual_prefix = prefix
    if mode == "append" and target_system_id:
        svc = _get_import_service()
        system = svc.system_service.get_system(target_system_id)
        if not system:
            raise HTTPException(404, f"系统 {target_system_id} 不存在")
        actual_prefix = system.prefix  # append 模式直接使用已有系统的 prefix（已含下划线）
    else:
        # 新建模式：标准化 prefix（3位大写字母 → 自动追加下划线）
        try:
            actual_prefix = normalize_prefix(prefix)
        except ValueError as e:
            raise HTTPException(400, str(e))

    # 验证数据
    repo = _get_repo()
    validator = ImportValidator(repo=repo)
    report = validator.validate(
        parse_result.entity_sheet,
        parse_result.relationship_sheet,
        mode=mode,
        target_prefix=actual_prefix,
    )

    if report.error_count > 0:
        return {
            "success": False,
            "message": f"验证未通过: {report.error_count} 个错误",
            "errors": [i.message for i in report.issues if i.severity.value == "error"],
            "entities_created": 0,
            "relationships_created": 0,
            "snapshot_id": None,
            "backup_available": False,
        }

    # 生成 Cypher
    gen_strategy = "MERGE" if mode == "append" else strategy
    generator = CypherGenerator(prefix=actual_prefix)
    cypher_batch = generator.generate(
        parse_result.entity_sheet,
        parse_result.relationship_sheet,
        strategy=gen_strategy,
    )

    # 带备份执行
    tx_manager = _get_tx_manager()
    result = tx_manager.execute_with_backup(cypher_batch, actual_prefix)

    # 更新 SQLite：仅在 Neo4j 完整导入成功后创建新系统记录
    if result.success and result.entities_created > 0 and mode == "new":
        svc = _get_import_service()
        # 如果 system_name 为空，从 prefix 生成默认名称
        display_name = system_name.strip() if system_name.strip() else f"未命名图谱 ({actual_prefix.rstrip('_')})"
        system = svc.system_service.create_system(
            name=display_name,
            description=description,
            prefix=actual_prefix,
        )
        node_total = repo.count_system_nodes(actual_prefix)
        rel_total = repo.count_system_relationships(actual_prefix)
        svc.system_service.update_counts(system.system_id, node_total, rel_total)

    # v3.6: 导入完成后自动初始化关系语义（仅新建/追加，不覆盖已有配置）
    if result.success and result.entities_created > 0:
        try:
            rel_types = repo.get_relation_types_by_prefix(actual_prefix)
            if rel_types:
                svc = _get_import_service()
                init_count = svc.system_service.init_semantics_from_neo4j(actual_prefix, rel_types)
                if init_count > 0:
                    logger.info(f"自动初始化 {init_count} 条关系语义 (prefix={actual_prefix})")
        except Exception as e:
            logger.warning(f"自动初始化关系语义失败 (可忽略): {e}")

        # v3.8: 图谱数据变更后主动失效 QueryService 的 Schema 缓存 + L1 结果缓存
        try:
            from backend.main import get_query_service
            qs = get_query_service()
            if qs:
                qs.invalidate_schema_cache(actual_prefix)
                qs.invalidate_semantics_cache(actual_prefix)
        except Exception:
            pass  # 缓存失效失败不阻塞导入流程

    return {
        "success": result.success,
        "entities_created": result.entities_created,
        "relationships_created": result.relationships_created,
        "snapshot_id": result.snapshot_id,
        "backup_available": result.backup_available,
        "errors": result.errors,
        "warnings": result.warnings,
        "message": result.message,
    }


# ══════════════════════════════════════════════════
# v3.5 新增: 备份/回滚管理
# ══════════════════════════════════════════════════

@router.post("/rollback/{snapshot_id}")
async def rollback_import(snapshot_id: str):
    """回滚到指定导入前快照，适用于 Excel 和关系数据库导入。"""
    tx_manager = _get_tx_manager()
    result = tx_manager.restore_from_backup(snapshot_id)
    if not result.get("success"):
        raise HTTPException(400, result.get("message", "回滚失败"))
    return result


@router.get("/backups")
async def list_backups():
    """★ v3.5: 列出所有备份快照。"""
    tx_manager = _get_tx_manager()
    return tx_manager.list_backups()


@router.delete("/backups/{snapshot_id}")
async def delete_backup(snapshot_id: str):
    """★ v3.5: 删除指定备份。"""
    tx_manager = _get_tx_manager()
    ok = tx_manager.delete_backup(snapshot_id)
    if not ok:
        raise HTTPException(404, f"快照 {snapshot_id} 不存在")
    return {"success": True, "message": f"已删除快照 {snapshot_id}"}


# ══════════════════════════════════════════════════
# v3.0 原有端点 (保持兼容)
# ══════════════════════════════════════════════════

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
    prefix: str = Form(""),
) -> ImportResult:
    """从 Excel 导入创建新系统（v3.5: 支持自定义 prefix）。"""
    if not file.filename or not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "仅支持 .xlsx / .xls 格式")
    content = await file.read()
    return _get_import_service().import_from_excel(
        content, system_name, description, prefix=prefix,
    )


@router.post("/excel/append")
async def append_excel(
    file: UploadFile = File(...),
    target_system_id: str = Form(...),
) -> ImportResult:
    """★ v3.5: Excel 追加数据到已有系统。"""
    if not file.filename or not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "仅支持 .xlsx / .xls 格式")
    content = await file.read()
    return _get_import_service().append_from_excel(content, target_system_id)


# ─── 关系数据库 ─────────────────────────────────

@router.post("/db/test")
async def test_connection(conn: DBConnection):
    """测试数据库连接."""
    try:
        ok = _get_import_service().test_connection(conn)
        return {"success": ok, "message": "连接成功" if ok else "连接失败"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    system_name: str = Body(...),
    description: str = Body(""),
    prefix: str = Body(""),
    relationship_mappings: list[RelationshipMapping] | None = None,
) -> ImportResult:
    """从数据库导入创建新系统（v3.5: 支持自定义 prefix）。"""
    return _get_import_service().import_from_db(
        conn, entity_mappings, system_name, description,
        prefix=prefix, relationship_mappings=relationship_mappings,
    )


@router.post("/db/append")
async def append_db(
    conn: DBConnection,
    entity_mappings: list[TableMapping],
    target_system_id: str = Body(...),
    relationship_mappings: list[RelationshipMapping] | None = Body(None),
) -> ImportResult:
    """★ v3.5: 数据库追加数据到已有系统。"""
    return _get_import_service().append_from_db(
        conn, entity_mappings, target_system_id, relationship_mappings,
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
