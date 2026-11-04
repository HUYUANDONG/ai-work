"""
用阿里云百炼决策模型做对话意图 Choice 路由。

模型：``decision-model-preview``（System One：choice / noul / score）。
环境变量：``DASHSCOPE_API_KEY``；文档：https://help.aliyun.com/zh/model-studio/decision-model-api
只返回有限选项 + confidence；默认参数与是否建任务仍由代码决定。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "decision-model-preview"
DEFAULT_REGION = "cn-beijing"
DEFAULT_COMPAT_ROOT = "https://dashscope.aliyuncs.com/compatible-mode"

INTENT_CRITERIA: dict[str, str] = {
    "EXPLOSION": (
        "筛爆品、爆品清单、潜力款、选品、冲GMV/冲量/清仓、本周盯谁。"
        "例句：近7天爆品、帮我筛爆品、按近30天冲GMV给我5个重点。"
        "带时间窗的爆品需求仍是 EXPLOSION，不是 CLARIFY。"
    ),
    "QUALITY": (
        "商品质检：亏本、缺货、退货、差评、质检报告。通常会说「质检」。"
        "例句：质检 SKU-001、看看谁亏本或缺货。"
    ),
    "SKU_DEEP": (
        "针对一两个已点名的 SKU 立刻分析/建议，不是全店筛选。"
        "例句：分析 SKU-001、这个品怎么样。"
    ),
    "FOLLOWUP": (
        "追问上一份分析结果：为什么排第几、分数什么意思、建议怎么理解。"
        "不是新开全店任务，也不是只改时间窗/目标/槽位。"
        "Session phase=AWAITING_ADVISE_CONFIRM 时，非「要/不用」的追问也属 FOLLOWUP。"
    ),
    "META": "问助手能做什么、怎么用、口径或政策。",
    "OUT_OF_SCOPE": (
        "写代码、爬虫、改价上下架、上架商品、一键发圈/发朋友圈、外网竞品、闲聊等本工作台做不了的事。"
        "上架与发圈已暂时砍掉，即使用户点名要求也是 OUT_OF_SCOPE。"
    ),
    "CLARIFY": (
        "爆品 / 质检 / 单品深挖之间含糊，或缺关键信息必须先问一句。"
        "「近7天爆品」「筛爆品」不是 CLARIFY。"
        "上一轮已是筛爆品/质检时，只改近7天/目标/槽位也不要 CLARIFY。"
        "Session phase=AWAITING_ADVISE_CONFIRM 时不要 CLARIFY 成新任务。"
    ),
}

WINDOW_CRITERIA: dict[str, str] = {
    "7": "User specified ~7 days: 近7天, 近一周, 本周, 最近一周, 七天.",
    "14": "User specified ~14 days: 近14天, 两周.",
    "30": "User explicitly specified ~30 days: 近30天, 一个月. Not the default guess.",
    "60": "User specified ~60 days: 近60天, 两个月.",
    "90": "User specified ~90 days: 近90天, 一季度, 三个月.",
    "UNSET": "No time window in the message. Do not pick 30 just because it is common.",
}


@dataclass(frozen=True)
class IntentDecision:
    """意图判定结果。"""

    intent: str
    confidence: float
    source: str
    probabilities: dict[str, float] | None = None
    error: str | None = None
    window_days: int | None = None


def build_systemone_url(
    *,
    base_url: str = "",
    workspace_id: str = "",
    region: str = DEFAULT_REGION,
) -> str:
    """
    拼百炼决策模型 System One 地址。

    Args:
        base_url: 完整覆盖（可到 compatible-mode 或 /v1/systemone）。
        workspace_id: 百炼业务空间 ID；有则走 ``{id}.{region}.maas.aliyuncs.com``。
        region: 地域，默认华北 2。

    Returns:
        str: POST 地址，以 ``/v1/systemone`` 结尾。
    """
    explicit = (base_url or "").strip().rstrip("/")
    if explicit:
        if explicit.endswith("/v1/systemone") or explicit.endswith("/systemone"):
            return explicit
        if explicit.endswith("/v1"):
            return f"{explicit}/systemone"
        return f"{explicit}/v1/systemone"
    workspace = (workspace_id or "").strip()
    rg = (region or DEFAULT_REGION).strip() or DEFAULT_REGION
    if workspace:
        return f"https://{workspace}.{rg}.maas.aliyuncs.com/compatible-mode/v1/systemone"
    return f"{DEFAULT_COMPAT_ROOT}/v1/systemone"


def _parse_choice_answer(body: dict) -> IntentDecision:
    """
    从 System One JSON 取出 intent Choice。

    Args:
        body: 百炼返回体。

    Returns:
        IntentDecision: source=decision。

    Raises:
        RuntimeError: 业务错误码或缺少 answers。
    """
    if body.get("code") and not body.get("answers"):
        raise RuntimeError(f"decision model error: {body.get('code')} {body.get('message')}")
    answers = body.get("answers")
    if not isinstance(answers, dict):
        raise RuntimeError("decision model missing answers")
    answer = answers.get("intent")
    if not isinstance(answer, dict):
        raise RuntimeError("decision model missing intent answer")
    choice = str(answer.get("choice") or "")
    confidence = float(answer.get("confidence") or 0.0)
    probs_raw = answer.get("probabilities") or {}
    probabilities = {str(k): float(v) for k, v in dict(probs_raw).items()}
    window_raw = answers.get("window") if isinstance(answers.get("window"), dict) else {}
    window_choice = str((window_raw or {}).get("choice") or "")
    return IntentDecision(
        intent=choice,
        confidence=confidence,
        source="decision",
        probabilities=probabilities,
        window_days=_window_days_from_choice(window_choice),
    )


def _window_days_from_choice(choice: str) -> int | None:
    """把 window Choice 转成天数；UNSET 视为未指定。"""
    raw = str(choice or "").strip().upper()
    if raw in {"", "UNSET", "UNSPECIFIED", "NONE", "NULL"}:
        return None
    try:
        days = int(raw)
    except ValueError:
        return None
    if 1 <= days <= 90:
        return days
    return None


def _run_decision_sync(
    *,
    state: str,
    model: str,
    api_key: str,
    endpoint: str,
) -> IntentDecision:
    """
    同步调用百炼决策模型 Choice。

    Args:
        state: 送给模型的精简状态文本。
        model: 模型名，通常 decision-model-preview。
        api_key: 百炼 API Key。
        endpoint: System One URL。

    Returns:
        IntentDecision: 选项与置信度。

    Raises:
        Exception: HTTP 或解析错误向上抛，由调用方决定降级。
    """
    payload = {
        "model": model,
        "state": state,
        "questions": {
            "intent": {
                "type": "choice",
                "instructions": (
                    "Primary intent for an ecommerce ops workbench that only "
                    "does store explosion campaign lists and product quality checks."
                ),
                "criteria": INTENT_CRITERIA,
            },
            "window": {
                "type": "choice",
                "instructions": (
                    "Time window in the latest user message only. "
                    "If the user says 近7天爆品, pick 7. Pick UNSET when omitted."
                ),
                "criteria": WINDOW_CRITERIA,
            },
        },
    }
    with httpx.Client(timeout=15.0, trust_env=False) as client:
        response = client.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if response.status_code >= 400:
        raise RuntimeError(
            f"decision model HTTP {response.status_code}: {response.text[:500]}"
        )
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError("decision model returned non-object JSON")
    return _parse_choice_answer(body)


def _use_systemone(*, base_url: str, workspace_id: str) -> bool:
    """是否走业务空间决策模型网关（无 Workspace ID 时 System One 会 404）。"""
    if (workspace_id or "").strip():
        return True
    root = (base_url or "").strip().lower()
    return "maas.aliyuncs.com" in root or "systemone" in root


def _parse_qwen_intent(text: str) -> IntentDecision:
    """
    解析千问返回的意图 JSON。

    Args:
        text: 模型正文。

    Returns:
        IntentDecision: source=qwen。

    Raises:
        RuntimeError: 无法解析。
    """
    raw = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fenced:
        raw = fenced.group(1).strip()
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"qwen intent JSON invalid: {raw[:200]}") from exc
    if not isinstance(body, dict):
        raise RuntimeError("qwen intent JSON is not an object")
    choice = str(body.get("intent") or "").strip()
    confidence = float(body.get("confidence") or 0.0)
    extra = body.get("window_days")
    window_days: int | None = None
    if extra not in (None, "", "UNSET"):
        try:
            parsed = int(extra)
            if 1 <= parsed <= 90:
                window_days = parsed
        except (TypeError, ValueError):
            window_days = None
    return IntentDecision(
        intent=choice,
        confidence=confidence,
        source="qwen",
        probabilities=None,
        window_days=window_days,
    )


def _run_qwen_intent_sync(
    *,
    state: str,
    api_key: str,
    chat_base_url: str,
    chat_model: str,
) -> IntentDecision:
    """
    用百炼 Chat Completions（qwen）做封闭意图分类。

    Args:
        state: 与决策模型相同的状态文本。
        api_key: 百炼 API Key。
        chat_base_url: OpenAI 兼容根路径。
        chat_model: 如 qwen-plus。

    Returns:
        IntentDecision: 选项与置信度。
    """
    options = "\n".join(f"- {name}: {desc}" for name, desc in INTENT_CRITERIA.items())
    payload = {
        "model": chat_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You classify ecommerce workbench intents. "
                    "Reply JSON only: "
                    "{\"intent\":\"<one>\",\"confidence\":0.0to1.0,\"window_days\":7ornull}. "
                    "intent must be exactly one of the option names. "
                    "window_days is 7/14/30/60/90 if the user specified a window "
                    "(近7天爆品 → 7), else null.\n"
                    f"{options}"
                ),
            },
            {"role": "user", "content": state},
        ],
    }
    url = f"{chat_base_url.rstrip('/')}/chat/completions"
    with httpx.Client(timeout=20.0, trust_env=False) as client:
        response = client.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if response.status_code >= 400:
        raise RuntimeError(
            f"qwen intent HTTP {response.status_code}: {response.text[:500]}"
        )
    body = response.json()
    try:
        content = str(body["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"unexpected qwen response: {body!r}") from exc
    return _parse_qwen_intent(content)


def _format_history(history: list[dict] | None, *, limit: int = 4) -> str:
    """把最近若干轮压成短文本给决策模型（业界常用短上下文，非全文报告）。"""
    rows: list[str] = []
    for item in (history or [])[-limit:]:
        role = str(item.get("role") or "user")
        content = str(item.get("content") or "").replace("\n", " ").strip()
        if not content:
            continue
        rows.append(f"{role}: {content[:120]}")
    return "\n".join(rows)


async def classify_with_decision(
    message: str,
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    min_confidence: float = 0.75,
    base_url: str = "",
    workspace_id: str = "",
    region: str = DEFAULT_REGION,
    history: list[dict] | None = None,
    last_intent: str | None = None,
    session_state: dict | None = None,
    chat_base_url: str = "",
    chat_model: str = "qwen-plus",
) -> IntentDecision:
    """
    异步包装意图分类；有 Workspace 走决策模型，否则走千问封闭分类。

    Args:
        message: 用户原文。
        api_key: DASHSCOPE_API_KEY。
        model: 决策模型名。
        min_confidence: 低于此值则 intent=CLARIFY。
        base_url: 可选网关覆盖。
        workspace_id: 百炼业务空间 ID。
        region: 地域。
        history: 本会话最近轮次。
        last_intent: 上一轮任务意图。
        session_state: 显式会话相位快照（``build_router_snapshot``）。
        chat_base_url: 千问 Chat Completions 根路径。
        chat_model: 千问模型名。

    Returns:
        IntentDecision: 最终用于路由的意图。
    """
    from harness.memory.dialog_state import format_router_state

    history_text = _format_history(history)
    session_block = format_router_state(session_state)
    state = (
        "Workbench capabilities: explosion campaign from SKU window metrics; "
        "quality inspection. Not for coding, listing, or external crawl.\n"
        "Routing policy: rule gates first; then classify with session phase; "
        "do not invent scores; expensive advise is a separate step.\n"
        "If the user only supplies a time window / goal / slot count after an "
        "explosion or quality turn, keep that previous intent.\n"
        f"{session_block}\n"
        f"Recent conversation (truncated):\n{history_text or '(empty)'}\n"
        f"User message:\n{(message or '').strip()}"
    )
    if _use_systemone(base_url=base_url, workspace_id=workspace_id):
        endpoint = build_systemone_url(
            base_url=base_url,
            workspace_id=workspace_id,
            region=region,
        )
        decision = await asyncio.to_thread(
            _run_decision_sync,
            state=state,
            model=model,
            api_key=api_key,
            endpoint=endpoint,
        )
    else:
        chat_root = (chat_base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1").strip()
        decision = await asyncio.to_thread(
            _run_qwen_intent_sync,
            state=state,
            api_key=api_key,
            chat_base_url=chat_root,
            chat_model=chat_model or "qwen-plus",
        )
    if decision.confidence < min_confidence:
        return IntentDecision(
            intent="CLARIFY",
            confidence=decision.confidence,
            source=f"{decision.source}_low_confidence",
            probabilities=decision.probabilities,
            error=None,
            window_days=decision.window_days,
        )
    if decision.intent not in INTENT_CRITERIA:
        return IntentDecision(
            intent="CLARIFY",
            confidence=decision.confidence,
            source=f"{decision.source}_invalid_choice",
            probabilities=decision.probabilities,
            error=f"unexpected choice: {decision.intent}",
            window_days=decision.window_days,
        )
    return decision


def classify_with_rules_fallback(
    message: str,
    *,
    last_intent: str | None = None,
) -> IntentDecision:
    """
    无 Key / 决策模型失败时的规则降级（仅本地兜底）。

    Args:
        message: 用户原文。
        last_intent: 上一轮任务意图。

    Returns:
        IntentDecision: source=rules_fallback。
    """
    from agents.chat.intent import classify_message_rules, parse_time_window_days

    intent = classify_message_rules(message, last_intent=last_intent)
    return IntentDecision(
        intent=intent,
        confidence=0.0,
        source="rules_fallback",
        probabilities=None,
        window_days=parse_time_window_days(message),
    )


def overlay_keyword_intent(
    decision: IntentDecision,
    message: str,
    last_intent: str | None,
) -> IntentDecision:
    """
    关键词已明确时，纠正决策模型的 CLARIFY / OUT_OF_SCOPE。

    Args:
        decision: 模型判定。
        message: 用户原文。
        last_intent: 上一轮任务意图。

    Returns:
        IntentDecision: 可能改写 intent，保留 window_days。
    """
    from agents.chat.intent import classify_message_rules

    if decision.intent not in {"CLARIFY", "OUT_OF_SCOPE"}:
        return decision
    rules = classify_message_rules(message, last_intent=last_intent)
    if rules not in {"EXPLOSION", "QUALITY", "SKU_DEEP", "META"}:
        return decision
    return IntentDecision(
        intent=rules,
        confidence=max(decision.confidence, 0.8),
        source=f"{decision.source}+rules",
        probabilities=decision.probabilities,
        error=decision.error,
        window_days=decision.window_days,
    )


def continue_previous_task(
    decision: IntentDecision,
    message: str,
    last_intent: str | None,
) -> IntentDecision:
    """
    澄清/追问若只是改参数，则继承上一轮任务意图。

    Args:
        decision: 原始判定。
        message: 用户原文。
        last_intent: 上一轮 EXPLOSION/QUALITY。

    Returns:
        IntentDecision: 可能改写 intent。
    """
    from agents.chat.intent import is_parameter_followup, parse_time_window_days

    if last_intent not in {"EXPLOSION", "QUALITY"}:
        return decision
    if decision.intent in {"EXPLOSION", "QUALITY", "SKU_DEEP", "META", "OUT_OF_SCOPE"}:
        return decision
    if not is_parameter_followup(message):
        return decision
    return IntentDecision(
        intent=last_intent,
        confidence=decision.confidence,
        source=f"{decision.source}+context",
        probabilities=decision.probabilities,
        error=decision.error,
        window_days=decision.window_days or parse_time_window_days(message),
    )


async def resolve_intent(
    message: str,
    *,
    api_key: str,
    enabled: bool,
    model: str,
    min_confidence: float,
    allow_rules_fallback: bool,
    base_url: str = "",
    workspace_id: str = "",
    region: str = DEFAULT_REGION,
    history: list[dict] | None = None,
    last_intent: str | None = None,
    session_state: dict | None = None,
    chat_base_url: str = "",
    chat_model: str = "qwen-plus",
) -> IntentDecision:
    """
    统一入口：意图只走大模型（决策模型 / 千问），不做关键词事后纠偏。

    Args:
        message: 用户原文。
        api_key: DASHSCOPE_API_KEY。
        enabled: 是否启用决策模型。
        model: 模型名。
        min_confidence: 置信度门槛。
        allow_rules_fallback: 仅无 Key / 调用失败时是否用规则兜底；默认应 false。
        base_url: 可选网关覆盖。
        workspace_id: 百炼业务空间 ID。
        region: 地域。
        history: 本会话最近轮次。
        last_intent: 上一轮任务意图（供模型上下文，不本地改写结果）。
        session_state: 显式会话相位快照。
        chat_base_url: 千问 Chat Completions 根路径。
        chat_model: 千问模型名。

    Returns:
        IntentDecision: 路由意图。
    """
    if not enabled or not (api_key or "").strip():
        if allow_rules_fallback:
            return classify_with_rules_fallback(message, last_intent=last_intent)
        return IntentDecision(
            intent="CLARIFY",
            confidence=0.0,
            source="decision_disabled",
            error="DASHSCOPE_API_KEY missing or decision model disabled",
        )

    try:
        return await classify_with_decision(
            message,
            api_key=api_key,
            model=model,
            min_confidence=min_confidence,
            base_url=base_url,
            workspace_id=workspace_id,
            region=region,
            history=history,
            last_intent=last_intent,
            session_state=session_state,
            chat_base_url=chat_base_url,
            chat_model=chat_model,
        )
    except Exception as exc:  # noqa: BLE001 — 降级路径需吞掉并记录
        logger.exception("Decision model intent classification failed: %s", exc)
        if allow_rules_fallback:
            fb = classify_with_rules_fallback(message, last_intent=last_intent)
            return IntentDecision(
                intent=fb.intent,
                confidence=0.0,
                source="rules_fallback_after_error",
                error=str(exc),
            )
        return IntentDecision(
            intent="CLARIFY",
            confidence=0.0,
            source="decision_error",
            error=str(exc),
        )
