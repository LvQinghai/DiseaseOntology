"""本体编辑器服务 —— v3.0: prefix 驱动，短标签名对外透明."""

import re

from fastapi import HTTPException

from backend.repositories.neo4j_repository import Neo4jRepository
from backend.utils.label_utils import strip_prefix
from backend.models.editor import (
    CreateEntityRequest,
    UpdateEntityRequest,
    EntityResponse,
    CreateRelationshipRequest,
    UpdateRelationshipRequest,
    RelationshipResponse,
    NodeSearchResult,
    RelationshipBrief,
    DeletionCheckResult,
    RelationshipInstanceSummary,
)


def _validate_entity_name(name: str) -> str:
    """校验节点名称."""
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="节点名称不能为空")
    if len(name) > 200:
        raise HTTPException(status_code=400, detail="节点名称不能超过 200 字符")
    return name


def _validate_label(label: str) -> str:
    """校验标签格式（v3.0: 短标签名，不含前缀）."""
    label = label.strip()
    if not label:
        raise HTTPException(status_code=400, detail="标签不能为空")
    if not re.match(r"^[A-Za-z\u4e00-\u9fa5][A-Za-z0-9_\u4e00-\u9fa5]*$", label):
        raise HTTPException(status_code=400, detail="标签格式不合法（仅支持字母/中文/数字/下划线）")
    return label


def _validate_properties(properties: dict) -> dict:
    """校验属性."""
    if not properties:
        return {}
    for key in properties:
        if not key or not key.strip():
            raise HTTPException(status_code=400, detail="属性名不能为空")
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key.strip()):
            raise HTTPException(
                status_code=400,
                detail=f"属性名 '{key}' 含非法字符（仅支持字母/数字/下划线，且以字母或下划线开头）",
            )
    return {k.strip(): v for k, v in properties.items()}


class EditorService:
    """本体编辑器服务"""

    def __init__(self, repo: Neo4jRepository):
        self._repo = repo

    # ==================== 实体 CRUD ====================

    def create_entity(self, req: CreateEntityRequest, prefix: str) -> EntityResponse:
        """创建实体节点（label 为短标签名，自动拼接 prefix）。"""
        label = _validate_label(req.label)
        name = _validate_entity_name(req.name)
        props = _validate_properties(req.properties)
        props["name"] = name

        existing = self._repo.find_node_by_name(name, label, prefix)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"节点 '{name}' ({label}) 已存在",
            )

        result = self._repo.create_node(label, props, prefix)
        rel_count = self._repo.get_node_relationship_count(result["element_id"])
        return EntityResponse(
            element_id=result["element_id"],
            labels=result["labels"],
            name=result["properties"].get("name", ""),
            properties=result["properties"],
            relationship_count=rel_count,
        )

    def update_entity(self, element_id: str, req: UpdateEntityRequest,
                      prefix: str) -> EntityResponse:
        """更新实体节点."""
        node = self._repo.get_node_by_id(element_id)
        if not node:
            raise HTTPException(status_code=404, detail=f"节点 {element_id} 不存在")

        if req.name is not None:
            name = _validate_entity_name(req.name)
            self._repo.set_node_name(element_id, name)

        if req.label is not None:
            label = _validate_label(req.label)
            self._repo.update_node_label(element_id, label, prefix)

        if req.properties is not None:
            props = _validate_properties(req.properties)
            if "name" in props:
                name = _validate_entity_name(props.pop("name"))
                self._repo.set_node_name(element_id, name)
            if props:
                self._repo.update_node_properties(element_id, props)

        updated = self._repo.get_node_by_id(element_id)
        rel_count = self._repo.get_node_relationship_count(element_id)
        return EntityResponse(
            element_id=updated["element_id"],
            labels=updated["labels"],
            name=updated["properties"].get("name", ""),
            properties=updated["properties"],
            relationship_count=rel_count,
        )

    def delete_entity(self, element_id: str) -> dict:
        """删除实体节点."""
        node = self._repo.get_node_by_id(element_id)
        if not node:
            raise HTTPException(status_code=404, detail=f"节点 {element_id} 不存在")

        rel_count = self._repo.get_node_relationship_count(element_id)
        name = node["properties"].get("name", "")

        if rel_count > 0:
            rel_details = self._repo.get_node_relationships_detail(element_id)
            rel_list = ", ".join(
                f"{r['type']}(→{r['other_node_name']})" for r in rel_details[:5]
            )
            raise HTTPException(
                status_code=409,
                detail=f"无法删除 '{name}'：该节点仍有 {rel_count} 条关联关系（{rel_list} 等）。"
                       f"请先在左侧面板的'关系'目录下找到对应关系并逐个删除，"
                       f"或使用图谱视图删除关联关系后再重试。",
            )

        self._repo.delete_node(element_id)
        return {"deleted": True, "name": name, "relationship_count": 0}

    def check_entity_deletion(self, element_id: str) -> DeletionCheckResult:
        """校验节点是否可删除."""
        node = self._repo.get_node_by_id(element_id)
        if not node:
            raise HTTPException(status_code=404, detail=f"节点 {element_id} 不存在")

        name = node["properties"].get("name", "")
        rel_details = self._repo.get_node_relationships_detail(element_id)
        relationships = [
            RelationshipBrief(
                element_id=r["element_id"],
                type=r["type"],
                direction=r["direction"],
                other_node_name=r["other_node_name"],
                other_node_element_id=r["other_node_element_id"],
                other_node_label=r["other_node_label"],
            )
            for r in rel_details
        ]
        can_delete = len(relationships) == 0

        if can_delete:
            message = f"节点 '{name}' 无关联关系，可以安全删除。"
        else:
            message = (
                f"节点 '{name}' 仍有 {len(relationships)} 条关联关系，"
                f"无法直接删除。请先在左侧面板的'关系'目录下找到对应关系并逐个删除，"
                f"或使用图谱视图删除关联关系后再重试。"
            )

        return DeletionCheckResult(
            can_delete=can_delete,
            name=name,
            relationship_count=len(relationships),
            relationships=relationships,
            message=message,
        )

    def get_entity(self, element_id: str) -> EntityResponse:
        """获取实体详情."""
        node = self._repo.get_node_by_id(element_id)
        if not node:
            raise HTTPException(status_code=404, detail=f"节点 {element_id} 不存在")
        rel_count = self._repo.get_node_relationship_count(element_id)
        return EntityResponse(
            element_id=node["element_id"],
            labels=node["labels"],
            name=node["properties"].get("name", ""),
            properties=node["properties"],
            relationship_count=rel_count,
        )

    # ==================== 属性操作 ====================

    def set_properties(self, element_id: str, properties: dict) -> EntityResponse:
        """批量设置属性."""
        node = self._repo.get_node_by_id(element_id)
        if not node:
            raise HTTPException(status_code=404, detail=f"节点 {element_id} 不存在")

        props = _validate_properties(properties)
        if "name" in props:
            name = _validate_entity_name(props.pop("name"))
            self._repo.set_node_name(element_id, name)
        if props:
            self._repo.update_node_properties(element_id, props)

        updated = self._repo.get_node_by_id(element_id)
        rel_count = self._repo.get_node_relationship_count(element_id)
        return EntityResponse(
            element_id=updated["element_id"],
            labels=updated["labels"],
            name=updated["properties"].get("name", ""),
            properties=updated["properties"],
            relationship_count=rel_count,
        )

    def delete_property(self, element_id: str, key: str) -> EntityResponse:
        """删除节点属性."""
        node = self._repo.get_node_by_id(element_id)
        if not node:
            raise HTTPException(status_code=404, detail=f"节点 {element_id} 不存在")
        self._repo.delete_node_property(element_id, key)
        updated = self._repo.get_node_by_id(element_id)
        rel_count = self._repo.get_node_relationship_count(element_id)
        return EntityResponse(
            element_id=updated["element_id"],
            labels=updated["labels"],
            name=updated["properties"].get("name", ""),
            properties=updated["properties"],
            relationship_count=rel_count,
        )

    # ==================== 关系 CRUD ====================

    def create_relationship(self, req: CreateRelationshipRequest,
                            prefix: str) -> RelationshipResponse:
        """创建节点间关系（type 为短类型名，自动拼接 prefix）。"""
        src_id = req.source_element_id.strip() if req.source_element_id else ""
        tgt_id = req.target_element_id.strip() if req.target_element_id else ""

        has_src = bool(src_id)
        has_tgt = bool(tgt_id)
        if has_src != has_tgt:
            raise HTTPException(status_code=400, detail="源节点和目标节点需要同时填写或同时留空")
        if not has_src and not has_tgt:
            raise HTTPException(status_code=400, detail="请至少提供源节点和目标节点")

        source = self._repo.get_node_by_id(src_id)
        if not source:
            raise HTTPException(status_code=404, detail=f"源节点 {src_id} 不存在")

        target = self._repo.get_node_by_id(tgt_id)
        if not target:
            raise HTTPException(status_code=404, detail=f"目标节点 {tgt_id} 不存在")

        rel_type = _validate_label(req.type)

        existing = self._repo.find_relationship(src_id, tgt_id, rel_type, prefix)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"关系 {source['properties'].get('name','')} "
                       f"→[{rel_type}]→ {target['properties'].get('name','')} 已存在",
            )

        props = _validate_properties(req.properties)
        result = self._repo.create_relationship(src_id, tgt_id, rel_type, props, prefix)

        return RelationshipResponse(
            element_id=result["element_id"],
            type=result["type"],
            source_id=result["source_id"],
            source_name=result["source_name"],
            target_id=result["target_id"],
            target_name=result["target_name"],
            properties=result["properties"],
        )

    def get_relationship(self, rel_element_id: str) -> RelationshipResponse:
        """获取关系详情."""
        result = self._repo.get_relationship_by_id(rel_element_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"关系 {rel_element_id} 不存在")
        return RelationshipResponse(
            element_id=result["element_id"],
            type=result["type"],
            source_id=result["source_id"],
            source_name=result["source_name"],
            target_id=result["target_id"],
            target_name=result["target_name"],
            properties=result["properties"],
        )

    def update_relationship(self, rel_element_id: str,
                            req: UpdateRelationshipRequest) -> RelationshipResponse:
        """更新关系."""
        rel = self._repo.get_relationship_by_id(rel_element_id)
        if not rel:
            raise HTTPException(status_code=404, detail=f"关系 {rel_element_id} 不存在")

        rel_type = _validate_label(req.type) if req.type is not None else None
        props = _validate_properties(req.properties) if req.properties is not None else None

        result = self._repo.update_relationship_full(
            rel_element_id,
            source_id=req.source_element_id,
            target_id=req.target_element_id,
            rel_type=rel_type,
            properties=props,
        )

        return RelationshipResponse(
            element_id=result["element_id"],
            type=result["type"],
            source_id=result["source_id"],
            source_name=result["source_name"],
            target_id=result["target_id"],
            target_name=result["target_name"],
            properties=result["properties"],
        )

    def delete_relationship(self, rel_element_id: str) -> dict:
        """删除关系."""
        deleted = self._repo.delete_relationship(rel_element_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"关系 {rel_element_id} 不存在")
        return {"deleted": True}

    def get_relationship_instances(self, rel_type: str, prefix: str,
                                   limit: int = 200) -> list[RelationshipInstanceSummary]:
        """获取指定关系类型的所有实例."""
        results = self._repo.get_relationship_instances(rel_type, prefix, limit)
        return [
            RelationshipInstanceSummary(
                element_id=r.get("element_id", ""),
                source_name=r.get("source_name", ""),
                source_label=r.get("source_label", ""),
                target_name=r.get("target_name", ""),
                target_label=r.get("target_label", ""),
            )
            for r in results
        ]

    # ==================== 元数据 ====================

    def get_available_labels(self, prefix: str) -> list[str]:
        """获取可用标签列表（完整标签名，带前缀）。"""
        return self._repo.get_all_labels(prefix)

    def get_available_relationship_types(self, prefix: str) -> list[str]:
        """获取可用关系类型列表（完整类型名，带前缀）。"""
        return self._repo.get_all_relationship_type_names(prefix)

    def search_nodes(self, keyword: str, prefix: str) -> list[NodeSearchResult]:
        """搜索节点."""
        results = self._repo.search_nodes(keyword, prefix)
        return [
            NodeSearchResult(
                element_id=r["element_id"],
                name=r.get("name", ""),
                labels=r.get("labels", []),
            )
            for r in results
        ]
