"""
Layer 2: 数据验证器

功能:
- 格式验证（必填字段 / 数据类型）
- 完整性检查（缺失值）
- 重复检查（导入数据内部）
- 追加模式冲突检测（Neo4j 已有数据冲突）
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from backend.repositories.neo4j_repository import Neo4jRepository
from backend.services.excel_detector import ParsedSheet


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """验证问题"""
    severity: ValidationSeverity
    code: str                          # "MISSING_NAME" / "DUPLICATE_ENTITY" / ...
    message: str                       # 人类可读消息
    sheet_type: str                    # "entity" | "relationship"
    row_index: int | None = None       # Excel 行号
    field: str | None = None           # 涉及字段
    detail: dict | None = None         # 额外详情


@dataclass
class ValidationReport:
    """验证报告"""
    is_valid: bool = True
    entity_count: int = 0
    relationship_count: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)

    # 追加模式专用
    conflict_entities: list[dict] = field(default_factory=list)
    conflict_relationships: list[dict] = field(default_factory=list)

    # 检测摘要：告诉用户识别到了哪些 Sheet、列如何映射
    detection_summary: dict = field(default_factory=lambda: {
        "entity_sheet": None,       # {"sheet_name": "...", "column_map": {"label": "实体标签", ...}}
        "relationship_sheet": None,
        "unmatched_sheets": [],     # 未识别的 Sheet 名称
    })

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.INFO)

    def add_issue(self, issue: ValidationIssue):
        self.issues.append(issue)
        if issue.severity == ValidationSeverity.ERROR:
            self.is_valid = False


# ---------------------------------------------------------------------------
# 验证器
# ---------------------------------------------------------------------------

class ImportValidator:
    """导入数据验证器"""

    ENTITY_REQUIRED_FIELDS = ["label", "name"]
    RELATIONSHIP_REQUIRED_FIELDS = ["source_name", "type", "target_name"]
    MAX_PREVIEW_ENTITIES = 20   # 预览时最多返回的实体数

    def __init__(self, repo: Optional[Neo4jRepository] = None):
        self.repo = repo

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def validate(
        self,
        entity_sheet: Optional[ParsedSheet],
        relationship_sheet: Optional[ParsedSheet],
        mode: str = "new",                # "new" | "append"
        target_prefix: str | None = None,  # append 模式必填
    ) -> ValidationReport:
        """完整验证：格式 + 完整性 + 重复 + 引用完整性 + (追加模式) 冲突检测。"""
        report = ValidationReport()

        # Sheet 缺失提示
        if not entity_sheet:
            report.add_issue(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="NO_ENTITY_SHEET",
                message="未识别到实体 Sheet。请确保 Excel 中有包含「标签」和「名称」相关列的 Sheet",
                sheet_type="entity",
            ))
        if not relationship_sheet:
            report.add_issue(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="NO_RELATIONSHIP_SHEET",
                message="未识别到关系 Sheet（可选）。如需导入关系，请确保有包含「源实体」「关系类型」「目标实体」列的 Sheet",
                sheet_type="relationship",
            ))

        if entity_sheet:
            report.entity_count = entity_sheet.row_count
            report.detection_summary["entity_sheet"] = self._build_mapping_display(entity_sheet)
            self._validate_entity_format(entity_sheet, report)
            self._validate_entity_completeness(entity_sheet, report)
            self._validate_entity_duplicates(entity_sheet, report)

        if relationship_sheet:
            report.relationship_count = relationship_sheet.row_count
            report.detection_summary["relationship_sheet"] = self._build_mapping_display(relationship_sheet)
            self._validate_relationship_format(relationship_sheet, report)
            self._validate_relationship_completeness(relationship_sheet, report)
            self._validate_relationship_duplicates(relationship_sheet, report)

        # 引用完整性：关系引用的实体在实体 Sheet 中必须存在
        if entity_sheet and relationship_sheet:
            self._validate_referential_integrity(entity_sheet, relationship_sheet, report)

        # 追加模式：检测与 Neo4j 已有数据的冲突
        if mode == "append" and target_prefix and self.repo:
            self._check_neo4j_conflicts(entity_sheet, relationship_sheet, target_prefix, report)

        return report

    # ------------------------------------------------------------------
    # 格式验证
    # ------------------------------------------------------------------

    def _validate_entity_format(self, sheet: ParsedSheet, report: ValidationReport):
        for row in sheet.rows:
            row_idx = row.get("_row")
            label = row.get("label")
            name = row.get("name")

            if not label or (isinstance(label, str) and label.strip() == ""):
                report.add_issue(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="MISSING_LABEL",
                    message="实体标签(label)不能为空",
                    sheet_type="entity",
                    row_index=row_idx,
                    field="label",
                ))
            if not name or (isinstance(name, str) and name.strip() == ""):
                report.add_issue(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="MISSING_NAME",
                    message="实体名称(name)不能为空",
                    sheet_type="entity",
                    row_index=row_idx,
                    field="name",
                ))

    def _validate_relationship_format(self, sheet: ParsedSheet, report: ValidationReport):
        for row in sheet.rows:
            row_idx = row.get("_row")
            source = row.get("source_name")
            rel_type = row.get("type")
            target = row.get("target_name")

            if not source or (isinstance(source, str) and source.strip() == ""):
                report.add_issue(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="MISSING_SOURCE",
                    message="源实体(source_name)不能为空",
                    sheet_type="relationship",
                    row_index=row_idx,
                    field="source_name",
                ))
            if not rel_type or (isinstance(rel_type, str) and rel_type.strip() == ""):
                report.add_issue(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="MISSING_TYPE",
                    message="关系类型(type)不能为空",
                    sheet_type="relationship",
                    row_index=row_idx,
                    field="type",
                ))
            if not target or (isinstance(target, str) and target.strip() == ""):
                report.add_issue(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="MISSING_TARGET",
                    message="目标实体(target_name)不能为空",
                    sheet_type="relationship",
                    row_index=row_idx,
                    field="target_name",
                ))

    # ------------------------------------------------------------------
    # 完整性检查（额外属性中的缺失值）
    # ------------------------------------------------------------------

    def _validate_entity_completeness(self, sheet: ParsedSheet, report: ValidationReport):
        # 检查实体是否有除 label/name 外的属性列为空
        for row in sheet.rows:
            row_idx = row.get("_row")
            for key, val in row.items():
                if key in ("_row", "label", "name"):
                    continue
                if val is None or (isinstance(val, str) and val.strip() == ""):
                    report.add_issue(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        code="EMPTY_PROPERTY",
                        message=f"实体的属性 '{key}' 为空",
                        sheet_type="entity",
                        row_index=row_idx,
                        field=key,
                    ))

    def _validate_relationship_completeness(self, sheet: ParsedSheet, report: ValidationReport):
        for row in sheet.rows:
            row_idx = row.get("_row")
            for key, val in row.items():
                if key in ("_row", "source_name", "type", "target_name"):
                    continue
                if val is None or (isinstance(val, str) and val.strip() == ""):
                    report.add_issue(ValidationIssue(
                        severity=ValidationSeverity.INFO,
                        code="EMPTY_REL_PROPERTY",
                        message=f"关系的属性 '{key}' 为空",
                        sheet_type="relationship",
                        row_index=row_idx,
                        field=key,
                    ))

    # ------------------------------------------------------------------
    # 重复检查（导入数据内部）
    # ------------------------------------------------------------------

    def _validate_entity_duplicates(self, sheet: ParsedSheet, report: ValidationReport):
        seen: dict[tuple[str, str], int] = {}
        for row in sheet.rows:
            label = str(row.get("label", "")).strip()
            name = str(row.get("name", "")).strip()
            row_idx = row.get("_row")
            key = (label, name)
            if key in seen:
                report.add_issue(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    code="DUPLICATE_ENTITY_IN_EXCEL",
                    message=f"实体 '{label}:{name}' 在当前数据中出现多次（首次在第 {seen[key]} 行）",
                    sheet_type="entity",
                    row_index=row_idx,
                    field="name",
                    detail={"first_row": seen[key], "label": label, "name": name},
                ))
            else:
                seen[key] = row_idx

    def _validate_relationship_duplicates(self, sheet: ParsedSheet, report: ValidationReport):
        seen: dict[tuple[str, str, str], int] = {}
        for row in sheet.rows:
            src = str(row.get("source_name", "")).strip()
            rtype = str(row.get("type", "")).strip()
            tgt = str(row.get("target_name", "")).strip()
            row_idx = row.get("_row")
            key = (src, rtype, tgt)
            if key in seen:
                report.add_issue(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    code="DUPLICATE_RELATIONSHIP",
                    message=f"关系 '{src} -[{rtype}]-> {tgt}' 在当前数据中出现多次",
                    sheet_type="relationship",
                    row_index=row_idx,
                    detail={"first_row": seen[key]},
                ))
            else:
                seen[key] = row_idx

    # ------------------------------------------------------------------
    # 引用完整性检查（关系引用的实体必须在实体 Sheet 中存在）
    # ------------------------------------------------------------------

    def _validate_referential_integrity(
        self,
        entity_sheet: ParsedSheet,
        relationship_sheet: ParsedSheet,
        report: ValidationReport,
    ):
        """检查关系 Sheet 中的源实体和目标实体在实体 Sheet 中是否存在。

        如果不存在，导入后关系端点会缺失，因此报 ERROR。
        """
        # 收集实体 Sheet 中所有实体名称
        entity_names: set[str] = set()
        for row in entity_sheet.rows:
            name = str(row.get("name", "")).strip()
            if name:
                entity_names.add(name)

        if not entity_names:
            return  # 实体 Sheet 本身就没数据，格式验证已报错

        # 检查关系引用的实体
        for row in relationship_sheet.rows:
            row_idx = row.get("_row")
            source = str(row.get("source_name", "")).strip()
            target = str(row.get("target_name", "")).strip()

            if source and source not in entity_names:
                report.add_issue(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="SOURCE_ENTITY_NOT_FOUND",
                    message=f"源实体「{source}」在实体 Sheet 中不存在，请检查名称是否一致",
                    sheet_type="relationship",
                    row_index=row_idx,
                    field="source_name",
                ))
            if target and target not in entity_names:
                report.add_issue(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="TARGET_ENTITY_NOT_FOUND",
                    message=f"目标实体「{target}」在实体 Sheet 中不存在，请检查名称是否一致",
                    sheet_type="relationship",
                    row_index=row_idx,
                    field="target_name",
                ))

    # ------------------------------------------------------------------
    # 追加模式：Neo4j 冲突检测
    # ------------------------------------------------------------------

    def _check_neo4j_conflicts(
        self,
        entity_sheet: Optional[ParsedSheet],
        relationship_sheet: Optional[ParsedSheet],
        prefix: str,
        report: ValidationReport,
    ):
        """检查导入数据与 Neo4j 已有数据的冲突。"""
        if not self.repo:
            return

        # 检查实体冲突
        if entity_sheet:
            for row in entity_sheet.rows:
                label = str(row.get("label", "")).strip()
                name = str(row.get("name", "")).strip()
                if not name:
                    continue
                existing = self.repo.get_node_by_name(name, f"{prefix}{label}")
                if existing:
                    new_props = {
                        k: v for k, v in row.items()
                        if k not in ("_row", "label", "name") and v is not None
                    }
                    existing_props = existing.get("properties", {})
                    conflict = {
                        "label": label,
                        "name": name,
                        "existing_props": existing_props,
                        "new_props": new_props,
                        "row_index": row.get("_row"),
                    }
                    report.conflict_entities.append(conflict)
                    report.add_issue(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        code="ENTITY_ALREADY_EXISTS",
                        message=f"实体 '{label}:{name}' 在目标图谱中已存在",
                        sheet_type="entity",
                        row_index=row.get("_row"),
                        field="name",
                        detail={
                            "existing_props": existing_props,
                            "new_props": new_props,
                        },
                    ))

        # 检查关系冲突
        if relationship_sheet:
            for row in relationship_sheet.rows:
                src = str(row.get("source_name", "")).strip()
                rtype = str(row.get("type", "")).strip()
                tgt = str(row.get("target_name", "")).strip()
                if not src or not rtype or not tgt:
                    continue
                existing_rel = self.repo.get_relationship_by_names(
                    src, tgt, f"{prefix}{rtype}"
                )
                if existing_rel:
                    report.conflict_relationships.append({
                        "source_name": src,
                        "type": rtype,
                        "target_name": tgt,
                        "row_index": row.get("_row"),
                        "existing_element_id": existing_rel.get("elementId", ""),
                    })
                    report.add_issue(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        code="RELATIONSHIP_ALREADY_EXISTS",
                        message=f"关系 '{src} -[{rtype}]-> {tgt}' 在目标图谱中已存在",
                        sheet_type="relationship",
                        row_index=row.get("_row"),
                    ))

    # ------------------------------------------------------------------
    # 预览数据裁剪（前端展示用）
    # ------------------------------------------------------------------

    @staticmethod
    def _build_mapping_display(sheet: ParsedSheet) -> dict:
        """构建用户友好的列映射展示：{原始表头: 标准字段名 or '属性'}。"""
        STANDARD_KEYS = {"label", "name", "source_name", "type", "target_name"}
        mapping_display: dict[str, str] = {}
        for key, idx in sheet.column_map.items():
            original = sheet.headers[idx] if idx < len(sheet.headers) else key
            if key in STANDARD_KEYS:
                mapping_display[original] = key
            else:
                mapping_display[original] = "属性"
        return {
            "sheet_name": sheet.sheet_name,
            "row_count": sheet.row_count,
            "column_mapping": mapping_display,
        }

    def get_preview(
        self,
        entity_sheet: Optional[ParsedSheet],
        relationship_sheet: Optional[ParsedSheet],
    ) -> dict:
        """获取预览数据（裁剪到 MAX_PREVIEW_ENTITIES 条）。"""
        result: dict = {
            "entities": [],
            "relationships": [],
            "entity_count": 0,
            "relationship_count": 0,
        }

        if entity_sheet:
            result["entity_count"] = entity_sheet.row_count
            for row in entity_sheet.rows[:self.MAX_PREVIEW_ENTITIES]:
                # 分离固定字段和属性字段
                item = {
                    "label": str(row.get("label", "")).strip(),
                    "name": str(row.get("name", "")).strip(),
                    "properties": {},
                    "_row": row.get("_row"),
                }
                for k, v in row.items():
                    if k not in ("_row", "label", "name") and v is not None:
                        item["properties"][k] = v
                result["entities"].append(item)

        if relationship_sheet:
            result["relationship_count"] = relationship_sheet.row_count
            for row in relationship_sheet.rows[:self.MAX_PREVIEW_ENTITIES]:
                item = {
                    "source_name": str(row.get("source_name", "")).strip(),
                    "type": str(row.get("type", "")).strip(),
                    "target_name": str(row.get("target_name", "")).strip(),
                    "properties": {},
                    "_row": row.get("_row"),
                }
                for k, v in row.items():
                    if k not in ("_row", "source_name", "type", "target_name") and v is not None:
                        item["properties"][k] = v
                result["relationships"].append(item)

        return result
