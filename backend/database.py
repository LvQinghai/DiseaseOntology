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
    from backend.models.system import Base, SystemModel, RelationSemanticModel

    # 创建表（幂等 —— 包含 v3.6 新表 relation_semantics）
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

    # v3.6: 为已有系统自动初始化关系语义（仅对 MED_ 等有预置语义的系统生效）
    try:
        _auto_seed_semantics(db_path)
    except Exception:
        pass  # 语义种子失败不阻塞启动


def _auto_seed_semantics(db_path: str) -> None:
    """v3.6: 为已有系统的关系类型自动填充预置语义（不覆盖已有配置）。"""
    from backend.services.system_service import SystemService
    from backend.repositories.neo4j_repository import Neo4jRepository
    from backend.models.system import UpsertRelationSemanticRequest
    from backend.config import settings as s  # noqa: N812

    # 只在 Neo4j 可用且系统有数据时才执行
    try:
        repo = Neo4jRepository(
            s.neo4j_uri, s.neo4j_user, s.neo4j_password,
        )
    except Exception:
        return

    system_svc = SystemService()

    # 获取所有系统及其关系类型
    session = get_session()
    try:
        systems = session.query(SystemModel).all()
    finally:
        session.close()

    from backend.services.query_service import get_preset_semantics

    for sys_row in systems:
        prefix = sys_row.prefix
        try:
            rel_types = repo.get_relation_types_by_prefix(prefix)
            if not rel_types:
                continue
            # 先填充预置语义
            preset_count = 0
            for rt in rel_types:
                preset = get_preset_semantics(rt)
                if preset:
                    system_svc.upsert_relation_semantic(
                        prefix,
                        UpsertRelationSemanticRequest(rel_type=rt, **preset),
                    )
                    preset_count += 1
            # 初始化其余类型
            count = system_svc.init_semantics_from_neo4j(prefix, rel_types)
            if preset_count > 0 or count > 0:
                total = preset_count + count
                print(f"  ✅ v3.6: 为 '{sys_row.name}' 初始化 {total} 条关系语义")
        except Exception as e:
            print(f"  ⚠️  语义种子 '{prefix}' 失败: {e}")
