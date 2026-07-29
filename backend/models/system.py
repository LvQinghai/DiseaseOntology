"""多系统管理相关模型 —— Pydantic (API 传输) + SQLAlchemy ORM (SQLite 存储)."""

from typing import Optional

from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


# ═══════════════════════════════════════════
# SQLAlchemy ORM 基类
# ═══════════════════════════════════════════

class Base(DeclarativeBase):
    pass


# ═══════════════════════════════════════════
# SQLite ORM 模型
# ═══════════════════════════════════════════

class SystemModel(Base):
    """system 表的 ORM 映射 —— 存储系统元数据于 SQLite."""
    __tablename__ = "systems"

    id = Column(Integer, primary_key=True, autoincrement=True)
    system_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    prefix = Column(String(10), unique=True, nullable=False, comment="Neo4j 标签/关系前缀，如 MED_")
    node_count = Column(Integer, default=0)
    relationship_count = Column(Integer, default=0)
    import_source = Column(String(50), default="manual")
    created_at = Column(String(30), default="")
    updated_at = Column(String(30), default="")


# ═══════════════════════════════════════════
# v3.6: 关系语义配置 (SQLite ORM)
# ═══════════════════════════════════════════

class RelationSemanticModel(Base):
    """relation_semantics 表的 ORM 映射 —— 存储每条关系的语义说明."""
    __tablename__ = "relation_semantics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prefix = Column(String(10), nullable=False, index=True, comment="关联 systems.prefix")
    rel_type = Column(String(200), nullable=False, comment="关系类型原名，如 TREATS")
    display_name = Column(String(200), default="", comment="显示名，如 治疗")
    description = Column(Text, default="", comment="语义描述文本")
    source_hint = Column(String(200), default="", comment="典型源实体标签")
    target_hint = Column(String(200), default="", comment="典型目标实体标签")
    cardinality = Column(String(30), default="", comment="映射基数: one_to_one / one_to_many / many_to_many")
    symmetry = Column(String(30), default="", comment="对称性: symmetric / asymmetric / reflexive")
    transitivity = Column(String(30), default="", comment="传递性: transitive / intransitive / none")
    created_at = Column(String(30), default="")
    updated_at = Column(String(30), default="")


# ═══════════════════════════════════════════
# Pydantic 数据传输模型
# ═══════════════════════════════════════════

class SystemInfo(BaseModel):
    """系统信息（API 响应）"""
    system_id: str
    prefix: str                          # ★ v3.0 核心：Neo4j 标签/关系前缀
    name: str
    description: str = ""
    node_count: int = 0
    relationship_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    import_source: str = ""              # "manual" | "excel" | "database"


class CreateSystemRequest(BaseModel):
    """创建系统请求"""
    name: str
    description: str = ""
    prefix: str = ""                     # ★ 可选：自定义前缀（空则自动生成）


class DeleteSystemRequest(BaseModel):
    """删除系统请求"""
    system_id: str


# ═══════════════════════════════════════════
# v3.6: 关系语义 Pydantic 模型
# ═══════════════════════════════════════════

class RelationSemanticInfo(BaseModel):
    """单条关系语义（API 响应）"""
    id: int = 0
    prefix: str = ""
    rel_type: str = ""
    display_name: str = ""
    description: str = ""
    source_hint: str = ""
    target_hint: str = ""
    cardinality: str = ""      # one_to_one / one_to_many / many_to_many
    symmetry: str = ""         # symmetric / asymmetric / reflexive
    transitivity: str = ""     # transitive / intransitive / none
    created_at: str = ""
    updated_at: str = ""


class UpsertRelationSemanticRequest(BaseModel):
    """创建或更新单条关系语义"""
    rel_type: str
    display_name: str = ""
    description: str = ""
    source_hint: str = ""
    target_hint: str = ""
    cardinality: str = ""
    symmetry: str = ""
    transitivity: str = ""


class SystemSemanticsResponse(BaseModel):
    """系统的全部关系语义配置"""
    prefix: str
    domain_description: str = ""
    semantics: list[RelationSemanticInfo] = []
