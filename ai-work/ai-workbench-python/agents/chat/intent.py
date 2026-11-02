"""
对话意图与缺参默认（规则版，不依赖 LLM）。
对话意图辅助：缺参默认、话术；规则分类仅作 Jev 降级。



正式路径见 ``agents.chat.jev_intent``（TypeSafe SDK / jev-latest）。

"""

from __future__ import annotations

from agents.chat import defaults as D


def classify_message_rules(message: str) -> str:
    """

    规则粗分类（Jev 不可用时的兜底，不作为正式方案）。



    Args:

        message: 用户原文。



    Returns:

        str: intent 枚举名。

    """

    text = (message or "").strip().lower()

    if not text:
        return "CLARIFY"

    out_scope_keys = (
        "爬虫",
        "写代码",
        "改价",
        "上架",
        "下架",
        "下单",
        "竞品价",
        "chatgpt",
        "翻译",
    )

    if any(k in text for k in out_scope_keys):
        return "OUT_OF_SCOPE"

    meta_keys = ("你能做什么", "你会什么", "怎么用", "什么口径", "帮助", "help")

    if any(k in text for k in meta_keys):
        return "META"

    from agents.chat.sku_parse import (
        extract_sku_ids,
        looks_like_sku_deep,
        looks_like_storewide_quality,
    )

    follow_keys = ("为什么", "第几", "刚才", "上一次", "这份报告", "先修再冲是什么")

    if any(k in text for k in follow_keys) and not any(
        k in text for k in ("再筛", "再跑", "重跑", "再质检")
    ):
        return "FOLLOWUP"

    if "质检" in text or (
        looks_like_storewide_quality(message) and any(
            k in text for k in ("亏本", "断货", "缺货", "退货", "有没有问题")
        )
    ):
        return "QUALITY"

    if looks_like_sku_deep(message) or (
        extract_sku_ids(message)
        and any(k in text for k in ("分析", "看看", "建议", "怎么样"))
    ):
        return "SKU_DEEP"

    explosion_keys = (
        "爆品",
        "潜力",
        "增长",
        "筛",
        "选品",
        "本周",
        "盯",
        "冲 gmv",
        "冲量",
        "清仓",
        "毛利",
    )

    if any(k in text for k in explosion_keys):
        return "EXPLOSION"

    return "CLARIFY"


def build_explosion_input(message: str) -> dict:
    """

    为爆品任务填充默认 input（时间窗 30 / GMV / 槽位 5）。



    Args:

        message: 用户原文（用于粗解析目标；正式可用第二次 Jev Choice）。



    Returns:

        dict: NEED_TASK.input。

    """

    text = (message or "").lower()

    goal = D.DEFAULT_GOAL_MODE

    if "清仓" in text or "清库存" in text:
        goal = "CLEARANCE"

    elif "毛利" in text or "利润" in text or "保利" in text:
        goal = "PROFIT"

    slots = D.DEFAULT_FOCUS_SLOTS

    for n in (3, 5, 8, 10):
        if f"盯 {n}" in text or f"盯{n}" in text or f"{n} 个" in text or f"{n}个" in text:
            slots = min(n, D.MAX_FOCUS_SLOTS)

            break

    return {
        "time_window_days": D.DEFAULT_TIME_WINDOW_DAYS,
        "goal_mode": goal,
        "focus_slots": slots,
        "top_n": D.DEFAULT_TOP_N,
        "on_sale_only": True,
        "category_id": None,
        "sku_ids": None,
    }


def out_of_scope_reply() -> str:
    """无关请求拒绝话术。"""

    return (
        "我只能帮你做店内**爆品作战清单**和**商品质检**（看增长、风险、本周盯谁）。"
        "你刚才说的不在能力范围内。"
        "可以试试：「按近 30 天冲 GMV，给我 5 个本周重点」或「质检一下 SKU-xxx」。"
    )


def default_window_notice() -> str:
    """未指定时间窗时的告知。"""

    return (
        f"未指定时间窗时，按**近 {D.DEFAULT_TIME_WINDOW_DAYS} 天对比前 "
        f"{D.DEFAULT_TIME_WINDOW_DAYS} 天**做正式分析。"
        "已按该口径准备任务；若要换窗口可以说一声再跑一版。"
    )


# 兼容旧调用名

classify_message = classify_message_rules
