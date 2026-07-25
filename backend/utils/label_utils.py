"""标签/关系类型的前缀工具函数 —— 用于 v3.0 前缀隔离方案.

Neo4j Community Edition 不支持多数据库，因此通过前缀隔离多套图谱：

- add_prefix("Disease", "MED_")  → "MED_Disease"
- strip_prefix("MED_Disease", "MED_") → "Disease"
"""

from typing import Sequence


def add_prefix(label: str, prefix: str) -> str:
    """为标签或关系类型添加系统前缀。

    Examples:
        add_prefix("Disease", "MED_") → "MED_Disease"
        add_prefix("TREATS", "MED_")  → "MED_TREATS"
        add_prefix("MED_Disease", "MED_") → "MED_Disease"  (幂等)
    """
    if label.startswith(prefix):
        return label
    return f"{prefix}{label}"


def strip_prefix(label: str, prefix: str) -> str:
    """从带前缀的标签或关系类型中剥离前缀。

    Examples:
        strip_prefix("MED_Disease", "MED_") → "Disease"
        strip_prefix("MED_TREATS", "MED_")  → "TREATS"
        strip_prefix("Disease", "MED_")      → "Disease"  (无前缀时原样返回)
    """
    if label.startswith(prefix):
        result = label[len(prefix):]
        return result if result else label
    return label


def strip_prefixes(labels: Sequence[str], prefix: str) -> list[str]:
    """批量剥离前缀。

    Examples:
        strip_prefixes(["MED_Disease", "MED_Symptom", "MED_Drug"], "MED_")
        → ["Disease", "Symptom", "Drug"]
    """
    return [strip_prefix(l, prefix) for l in labels]


def has_prefix(label: str, prefix: str) -> bool:
    """判断标签是否带有指定前缀。"""
    return label.startswith(prefix)


def get_prefix_labels(prefix: str, short_labels: Sequence[str]) -> list[str]:
    """将短标签列表批量添加前缀。

    Examples:
        get_prefix_labels("MED_", ["Disease", "Symptom"])
        → ["MED_Disease", "MED_Symptom"]
    """
    return [add_prefix(l, prefix) for l in short_labels]
