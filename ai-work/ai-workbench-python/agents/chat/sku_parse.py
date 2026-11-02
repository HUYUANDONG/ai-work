"""从用户消息解析 SKU ID。"""

from __future__ import annotations

import re

_SKU_TOKEN = re.compile(r"(?i)\bSKU[-_]?([A-Za-z0-9][A-Za-z0-9_-]{0,31})\b")


def extract_sku_ids(message: str, *, limit: int = 50) -> list[str]:
    """
    从消息中提取 SKU 列表（去重保序），统一为 ``SKU-xxx``。

    Args:
        message: 用户原文。
        limit: 最多返回条数。

    Returns:
        list[str]: sku_id 列表。
    """
    found: list[str] = []
    seen: set[str] = set()
    for m in _SKU_TOKEN.finditer(message or ""):
        sku = f"SKU-{m.group(1)}"
        key = sku.upper()
        if key not in seen:
            seen.add(key)
            found.append(sku)
    return found[:limit]


def looks_like_sku_deep(message: str) -> bool:
    """是否像单品深挖（有 SKU + 分析类动词，而非完整质检）。"""
    text = (message or "").strip()
    skus = extract_sku_ids(text)
    if not skus:
        return False
    if any(k in text for k in ("质检", "完整质检", "问题清单")):
        return False
    deep_keys = ("分析", "看看", "帮我看", "深挖", "解读", "建议", "怎么样", "如何")
    return any(k in text for k in deep_keys) or (len(skus) == 1 and "筛" not in text)


def looks_like_storewide_quality(message: str) -> bool:
    """全店问题品扫描（无指定 SKU）。"""
    text = (message or "").strip()
    if extract_sku_ids(text):
        return False
    keys = ("亏本", "断货", "缺货", "谁在亏", "哪些品", "全店", "有问题的")
    return any(k in text for k in keys)

