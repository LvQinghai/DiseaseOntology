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
