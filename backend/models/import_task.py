"""数据导入相关 Pydantic 模型."""

from pydantic import BaseModel


# ─── 数据库连接 ─────────────────────────────────

class DBConnection(BaseModel):
    """关系数据库连接信息"""
    db_type: str                        # "mysql" | "postgresql" | "mssql" | "oracle" | "sqlite"
    host: str
    port: int
    database: str
    user: str
    password: str


class TableInfo(BaseModel):
    """数据库表结构信息"""
    name: str
    columns: list[dict]                 # [{"name": "...", "type": "..."}]


# ─── 映射配置 ───────────────────────────────────

class TableMapping(BaseModel):
    """表→实体映射配置"""
    source_table: str                   # 源表名
    source_column: str                  # 源列名（用于 name 属性）
    target_label: str                   # 目标节点标签


class RelationshipMapping(BaseModel):
    """表→关系映射配置"""
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    relationship_type: str              # eg: "TREATS"


# ─── 导入请求 ───────────────────────────────────

class ImportFromExcelRequest(BaseModel):
    """Excel 导入请求"""
    system_name: str
    description: str = ""


class ImportFromDBRequest(BaseModel):
    """数据库导入请求"""
    connection: DBConnection
    entity_mappings: list[TableMapping]
    relationship_mappings: list[RelationshipMapping] = []
    system_name: str
    description: str = ""


# ─── 预览/结果 ──────────────────────────────────

class ImportPreviewData(BaseModel):
    """导入预览数据"""
    entities: list[dict]                # [{"label": "...", "name": "...", "properties": {...}}]
    relationships: list[dict]           # [{"type": "...", "source_name": "...", "target_name": "..."}]
    total_entities: int = 0
    total_relationships: int = 0


class ImportResult(BaseModel):
    """导入结果"""
    success: bool
    system_id: str = ""
    system_name: str = ""
    entities_created: int = 0
    relationships_created: int = 0
    message: str = ""
    errors: list[str] = []
