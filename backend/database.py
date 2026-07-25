"""SQLite 数据库连接管理 —— 用于存储系统元数据（SQLAlchemy 2.0 风格）."""

import os

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine(db_path: str) -> Engine:
    """获取或创建 SQLAlchemy 引擎（单例）。"""
    global _engine
    if _engine is None:
        _engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            connect_args={"check_same_thread": False},  # FastAPI 多线程兼容
        )
    return _engine


def init_session_factory(engine: Engine) -> None:
    """初始化 Session 工厂（需在首次 get_session 前调用）。"""
    global _SessionLocal
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session() -> Session:
    """获取一个新的 SQLAlchemy Session（调用方负责关闭）。"""
    global _SessionLocal
    if _SessionLocal is None:
        raise RuntimeError("数据库未初始化，请先调用 init_database()")
    return _SessionLocal()


def init_database(db_path: str) -> None:
    """初始化 SQLite 数据库。

    1. 创建所有 ORM 表
    2. 插入默认系统数据（如不存在）
    """
    from backend.config import settings

    # 确保数据目录存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    engine = get_engine(db_path)
    init_session_factory(engine)

    # 延迟导入避免循环依赖
    from backend.models.system import Base, SystemModel

    # 创建表（幂等）
    Base.metadata.create_all(bind=engine)

    # 种子数据：默认的疾病诊疗系统
    session = get_session()
    try:
        existing = session.query(SystemModel).filter_by(
            system_id=settings.DEFAULT_SYSTEM_ID
        ).first()
        if not existing:
            default = SystemModel(
                system_id=settings.DEFAULT_SYSTEM_ID,
                name=settings.DEFAULT_SYSTEM_NAME,
                description=settings.DEFAULT_SYSTEM_DESC,
                prefix=settings.DEFAULT_SYSTEM_PREFIX,
                import_source="原生数据",
            )
            session.add(default)
            session.commit()
            print(f"✅ SQLite: 默认系统 '{settings.DEFAULT_SYSTEM_NAME}' "
                  f"({settings.DEFAULT_SYSTEM_PREFIX}) 已创建")
        else:
            print(f"✅ SQLite: 默认系统已存在")
    finally:
        session.close()
