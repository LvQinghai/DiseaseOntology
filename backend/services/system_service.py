"""系统管理服务 —— v3.0: 基于 SQLAlchemy SQLite 存储元数据."""

import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.database import get_session
from backend.models.system import SystemModel, SystemInfo

# 保留前缀列表（不可用于业务系统）
_RESERVED_PREFIXES = {"SYS_", "META_", "ADMIN_"}


class SystemService:
    """系统管理服务 —— 所有系统元数据读写均通过 SQLite"""

    # ───────────── 查询 ─────────────

    def get_all_systems(self) -> list[SystemInfo]:
        """获取所有系统列表（从 SQLite）。"""
        session = get_session()
        try:
            rows = session.query(SystemModel).order_by(
                SystemModel.created_at.desc()
            ).all()
            return [self._to_info(r) for r in rows]
        finally:
            session.close()

    def get_system(self, system_id: str) -> SystemInfo | None:
        """获取单个系统信息。"""
        session = get_session()
        try:
            row = session.query(SystemModel).filter_by(
                system_id=system_id
            ).first()
            return self._to_info(row) if row else None
        finally:
            session.close()

    def get_prefix(self, system_id: str) -> str:
        """根据 system_id 获取 prefix（用于 Router 层解析）。"""
        system = self.get_system(system_id)
        if not system:
            raise ValueError(f"系统 '{system_id}' 不存在")
        return system.prefix

    # ───────────── 写操作 ─────────────

    def create_system(
        self, name: str, description: str = "",
        prefix: str = "", import_source: str = "manual",
    ) -> SystemInfo:
        """创建新系统（写入 SQLite）。

        - 自动分配 prefix（如果用户未指定或 prefix 冲突）。
        - 自动生成唯一 system_id。
        """
        session = get_session()
        try:
            existing_prefixes = {
                r.prefix for r in session.query(SystemModel.prefix).all()
            }
            if not prefix:
                prefix = self._generate_prefix(name, existing_prefixes)
            else:
                if prefix in existing_prefixes:
                    raise ValueError(f"前缀 '{prefix}' 已被其他系统使用")
                if prefix in _RESERVED_PREFIXES:
                    raise ValueError(f"前缀 '{prefix}' 为系统保留前缀，不可用于业务系统")

            # 生成唯一的 system_id
            system_id = self._slugify(name)
            existing = session.query(SystemModel).filter_by(
                system_id=system_id
            ).first()
            if existing:
                system_id = f"{system_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

            now = datetime.now(timezone.utc).isoformat()
            model = SystemModel(
                system_id=system_id,
                name=name.strip(),
                description=description,
                prefix=prefix,
                import_source=import_source,
                created_at=now,
                updated_at=now,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            return self._to_info(model)
        finally:
            session.close()

    def delete_system(self, system_id: str) -> bool:
        """删除系统（SQLite 删记录）。"""
        session = get_session()
        try:
            row = session.query(SystemModel).filter_by(
                system_id=system_id
            ).first()
            if not row:
                return False
            session.delete(row)
            session.commit()
            return True
        finally:
            session.close()

    def update_counts(self, system_id: str,
                      node_count: int, relationship_count: int) -> None:
        """更新系统节点/关系统计。"""
        session = get_session()
        try:
            row = session.query(SystemModel).filter_by(
                system_id=system_id
            ).first()
            if row:
                row.node_count = node_count
                row.relationship_count = relationship_count
                row.updated_at = datetime.now(timezone.utc).isoformat()
                session.commit()
        finally:
            session.close()

    # ───────────── 工具 ─────────────

    def _to_info(self, model: SystemModel) -> SystemInfo:
        """ORM 模型 → Pydantic 模型。"""
        return SystemInfo(
            system_id=model.system_id,
            prefix=model.prefix,
            name=model.name,
            description=model.description or "",
            node_count=model.node_count or 0,
            relationship_count=model.relationship_count or 0,
            created_at=model.created_at or "",
            updated_at=model.updated_at or "",
            import_source=model.import_source or "manual",
        )

    @staticmethod
    def _slugify(name: str) -> str:
        """将系统名称转为合法的 system_id。"""
        slug = name.strip().lower()
        slug = re.sub(r'\s+', '_', slug)
        slug = re.sub(r'[^a-z0-9_]', '', slug)
        return slug or "unnamed_system"

    @staticmethod
    def _generate_prefix(name: str, existing: set[str]) -> str:
        """根据系统名称自动生成唯一前缀。

        规则：
        1. 提取英文单词首字母（大写）
        2. 加下划线结尾
        3. 冲突时递增序号
        """
        chars = re.findall(r'[A-Za-z]', name)
        if chars:
            base = "".join([c.upper() for c in chars[:3]])
        else:
            base = "KG"  # Knowledge Graph fallback

        prefix = f"{base}_"
        if prefix not in existing and prefix not in _RESERVED_PREFIXES:
            return prefix

        for i in range(2, 20):
            alt = f"{base}{i}_"
            if alt not in existing and alt not in _RESERVED_PREFIXES:
                return alt

        # 极端兜底
        import string, random
        while True:
            prefix = "".join(random.choices(string.ascii_uppercase, k=3)) + "_"
            if prefix not in existing and prefix not in _RESERVED_PREFIXES:
                return prefix
