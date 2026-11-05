"""
对话意图辅助：缺参默认、话术，以及无上下文的规则粗分类。

正式路径见 ``agents.chat.decision_intent``：规则先判，判不出再交给带上下文的模型。
"""

from __future__ import annotations

import re
from typing import Any

from agents.chat import defaults as D

_NEW_INTENT_KEYS = (
    "爆品",
    "潜力",
    "选品",
    "质检",
    "亏本",
    "断货",
    "缺货",
    "退货",
    "分析 sku",
    "分析sku",
    "你能做什么",
    "你会什么",
    "怎么用",
    "爬虫",
    "写代码",
    "改价",
    "上架",
    "下架",
    "发圈",
    "一键发圈",
    "发朋友圈",
    "上架商品",
)

_EXPLOSION_KEYS = (
    "爆品",
    "潜力",
    "增长",
    "筛",
    "选品",
    "本周",
    "盯",
    "冲 gmv",
    "冲gmv",
    "冲量",
    "清仓",
    "毛利",
)

# 首句已明确要投放/作战建议 → 同轮 include_advise
_ADVISE_WANT_KEYS = (
    "建议",
    "投放",
    "怎么推",
    "怎么投",
    "放哪",
    "作战建议",
    "给建议",
    "出建议",
    "写建议",
    "推哪",
    "放哪个板块",
)

_ADVISE_AFFIRM_KEYS = (
    "要",
    "需要",
    "好的",
    "行",
    "可以",
    "给建议",
    "出建议",
    "写建议",
    "要建议",
    "来吧",
    "继续",
)

_ADVISE_DECLINE_KEYS = (
    "不用",
    "不要",
    "先这样",
    "暂不",
    "不需要",
    "下次再说",
    "算了",
)

ADVICE_OFFER_QUESTION = (
    "需要我结合日板块流量写投放建议吗？回复「要」或「不用」即可。"
)

_WINDOW_RE = re.compile(
    r"(?:近|最近|过去|前)?\s*(\d+)\s*(?:天|日)",
    re.IGNORECASE,
)
_CN_DIGIT = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
_CN_WINDOW_RE = re.compile(
    r"(?:近|最近|过去|前)?\s*([一二两三四五六七八九十])\s*(?:天|日)",
)
_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")


def parse_time_window_days(message: str) -> int | None:
    """
    从用户原文解析时间窗天数。

    Args:
        message: 用户原文。

    Returns:
        int | None: 1–90 的天数；无法解析则 None。
    """
    text = (message or "").strip().translate(_FULLWIDTH_DIGITS)
    if not text:
        return None
    if any(k in text for k in ("近一周", "最近一周", "过去一周", "本周")):
        return 7
    if re.search(r"(?:近|最近|过去)?\s*(?:两|二)\s*周", text):
        return 14
    match = _WINDOW_RE.search(text)
    if match:
        days = int(match.group(1))
        if 1 <= days <= 90:
            return days
    cn_match = _CN_WINDOW_RE.search(text)
    if cn_match:
        days = _CN_DIGIT.get(cn_match.group(1))
        if days is not None and 1 <= days <= 90:
            return days
    return None


def resolve_time_window_days(message: str, extra: int | None = None) -> int | None:
    """
    规则优先，决策模型抽出的天数作补充。

    Args:
        message: 用户原文。
        extra: 模型给出的天数。

    Returns:
        int | None: 1–90；都没有则 None。
    """
    parsed = parse_time_window_days(message)
    if parsed is not None:
        return parsed
    if extra is not None and 1 <= int(extra) <= 90:
        return int(extra)
    return None


def is_parameter_followup(message: str) -> bool:
    """
    是否只在改上一轮任务的参数（时间窗/目标/槽位），而不是新开一类意图。

    Args:
        message: 用户原文。

    Returns:
        bool: True 表示应继承上一轮 EXPLOSION/QUALITY。
    """
    text = (message or "").strip()
    if not text:
        return False
    lowered = text.lower()
    if any(k in lowered for k in _NEW_INTENT_KEYS):
        return False
    has_window = parse_time_window_days(text) is not None
    has_goal = any(k in text for k in ("清仓", "清库存", "毛利", "利润", "保利", "gmv", "GMV", "冲量"))
    has_slots = bool(re.search(r"(盯\s*\d+|\d+\s*个)", text))
    has_rerun = any(
        k in text
        for k in (
            "再跑",
            "重跑",
            "换窗口",
            "改成",
            "换成",
            "按这个",
            "按刚才",
            "再试",
            "再来一",
            "重新分析",
            "重新跑",
        )
    )
    return has_window or has_goal or has_slots or has_rerun


def is_retry_message(message: str) -> bool:
    """
    用户要重跑上一轮任务，而不是把话排进当前长任务队列。

    Args:
        message: 用户原文。

    Returns:
        bool: 「再试一次」等应开新任务。
    """
    text = (message or "").strip()
    if not text:
        return False
    return any(
        k in text
        for k in ("再试", "再跑", "重跑", "再来一", "重新分析", "重新跑", "再筛")
    )


def infer_last_task_intent(history: list[dict[str, Any]] | None) -> str | None:
    """
    从最近对话推断上一轮任务意图。

    Args:
        history: role/content/intent 列表，旧→新。

    Returns:
        str | None: EXPLOSION / QUALITY。
    """
    for item in reversed(history or []):
        intent = str(item.get("intent") or "").upper()
        if intent in {"EXPLOSION", "QUALITY"}:
            return intent
        content = str(item.get("content") or "")
        role = str(item.get("role") or "")
        if role != "assistant":
            continue
        if "已识别为质检" in content:
            return "QUALITY"
        if any(
            k in content
            for k in ("已生成分析任务", "目标模式", "本周槽位", "筛爆品", "对比前")
        ):
            return "EXPLOSION"
    return None


def classify_message_rules(message: str, *, last_intent: str | None = None) -> str:
    """
    规则粗分类（决策模型不可用时的兜底）。

    Args:
        message: 用户原文。
        last_intent: 本会话上一轮任务意图。

    Returns:
        str: intent 枚举名。
    """
    text = (message or "").strip().lower()
    if not text:
        return "CLARIFY"

    if last_intent in {"EXPLOSION", "QUALITY"} and is_parameter_followup(message):
        return last_intent

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
        "发圈",
        "一键发圈",
        "发朋友圈",
        "上架商品",
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
        looks_like_storewide_quality(message)
        and any(k in text for k in ("亏本", "断货", "缺货", "退货", "有没有问题"))
    ):
        return "QUALITY"

    if looks_like_sku_deep(message) or (
        extract_sku_ids(message)
        and any(k in text for k in ("分析", "看看", "建议", "怎么样"))
    ):
        return "SKU_DEEP"

    if any(k in text for k in _EXPLOSION_KEYS):
        return "EXPLOSION"

    if last_intent in {"EXPLOSION", "QUALITY"} and is_parameter_followup(message):
        return last_intent

    return "CLARIFY"


def wants_explosion_advise(message: str) -> bool:
    """
    用户是否在首句（或补参句）明确要求投放/作战建议。

    Args:
        message: 用户原文。

    Returns:
        bool: True 则任务同轮拉板块并用 LLM 写建议。
    """
    text = (message or "").strip().lower()
    if not text:
        return False
    return any(k in text for k in _ADVISE_WANT_KEYS)


def is_advise_affirm(message: str) -> bool:
    """
    榜单后确认「要建议」的短答（可带时间窗，如「近30天也要建议」）。

    Args:
        message: 用户原文。

    Returns:
        bool: 肯定续问。
    """
    text = (message or "").strip().lower()
    if not text or len(text) > 48:
        return False
    if any(k in text for k in _NEW_INTENT_KEYS):
        return False
    if any(k in text for k in _ADVISE_DECLINE_KEYS):
        return False
    return any(k in text for k in _ADVISE_AFFIRM_KEYS)


def is_advise_decline(message: str) -> bool:
    """
    榜单后明确不要建议。

    Args:
        message: 用户原文。

    Returns:
        bool: 否定续问。
    """
    text = (message or "").strip().lower()
    if not text or len(text) > 40:
        return False
    return any(k in text for k in _ADVISE_DECLINE_KEYS)


def build_explosion_input(message: str, base: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    为爆品任务填充 input；可叠加上一轮参数。

    Args:
        message: 用户原文。
        base: 上一轮任务 input。

    Returns:
        dict: NEED_TASK.input。
    """
    data: dict[str, Any] = {
        "time_window_days": D.DEFAULT_TIME_WINDOW_DAYS,
        "goal_mode": D.DEFAULT_GOAL_MODE,
        "focus_slots": D.DEFAULT_FOCUS_SLOTS,
        "top_n": D.DEFAULT_TOP_N,
        "on_sale_only": True,
        "category_id": None,
        "sku_ids": None,
        "include_advise": False,
    }
    if base:
        for key, value in base.items():
            if key in data and value is not None and key != "include_advise":
                data[key] = value

    text = (message or "").lower()
    window = parse_time_window_days(message)
    if window is not None:
        data["time_window_days"] = window

    if "清仓" in text or "清库存" in text:
        data["goal_mode"] = "CLEARANCE"
    elif "毛利" in text or "利润" in text or "保利" in text:
        data["goal_mode"] = "PROFIT"
    elif "gmv" in text or "冲量" in text:
        data["goal_mode"] = "GMV"

    for n in (3, 5, 8, 10):
        if f"盯 {n}" in text or f"盯{n}" in text or f"{n} 个" in text or f"{n}个" in text:
            data["focus_slots"] = min(n, D.MAX_FOCUS_SLOTS)
            break

    data["include_advise"] = wants_explosion_advise(message)
    return data


def window_notice(days: int, *, user_specified: bool) -> str:
    """
    时间窗告知。

    Args:
        days: 实际使用的天数。
        user_specified: 是否由用户本轮指定。

    Returns:
        str: 回复前缀。
    """
    if user_specified:
        return f"已按**近 {days} 天对比前 {days} 天**准备任务。"
    return (
        f"未指定时间窗时，按**近 {days} 天对比前 {days} 天**做正式分析。"
        "已按该口径准备任务；若要换窗口可以说一声再跑一版。"
    )


def out_of_scope_reply() -> str:
    """无关请求拒绝话术。"""
    return (
        "我只能帮你做店内**爆品作战清单**和**商品质检**（看增长、风险、本周盯谁）。"
        "**上架商品**和**一键发圈**已暂时下线，不在能力范围内。"
        "可以试试：「按近 30 天冲 GMV，给我 5 个本周重点」或「质检一下 SKU-xxx」。"
    )


def default_window_notice() -> str:
    """未指定时间窗时的告知。"""
    return window_notice(D.DEFAULT_TIME_WINDOW_DAYS, user_specified=False)


# 兼容旧调用名
classify_message = classify_message_rules
