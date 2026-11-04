"""
分层记忆（业界常见四层，精简版）：

- working: 最近若干轮对话
- summary: 更早轮次的滚动摘要（禁止 summary-of-summary 反复失真：只追加一次压缩）
- archive: 报告/任务指针（不可变引用）
- constraints: 跨轮约束约束（可 upsert，支持 supersede 推翻）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.memory.tokens import TokenBudget


@dataclass
class Constraint:
    """跨轮约束。"""

    key: str
    value: str
    active: bool = True


@dataclass
class SessionMemory:
    """
    单会话记忆。

    Attributes:
        conversation_id: 会话 ID。
        working: 最近消息 {role, content}。
        summary: 压缩后的旧对话摘要（可空）。
        archives: 归档指针列表。
        constraints: 约束（错误决策可 supersede）。
        last_intent: 上一轮任务意图（EXPLOSION/QUALITY）。
        last_task_input: 上一轮任务入参，供短句补参叠加。
        advice_offer_pending: 爆品榜单已出，等待用户确认是否写投放建议。
        awaiting_clarify: 上一轮返回了 clarify_pending。
        last_report_task_id: 最近完成任务。
        episodes: 已完成任务短摘要。
        ops_phase: 运营流水线相位（IDLE / 等建议 / 等文案 / DONE）。
        ops_context: 运营流水线中间态（candidates / inventory 等）。
    """

    conversation_id: str
    working: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    archives: list[dict[str, Any]] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    last_intent: str | None = None
    last_task_input: dict[str, Any] = field(default_factory=dict)
    advice_offer_pending: bool = False
    awaiting_clarify: bool = False
    last_report_task_id: str | None = None
    episodes: list[dict[str, Any]] = field(default_factory=list)
    # 摘要已覆盖到的最大消息 id；Java 据此只回放之后的原文
    summary_through_message_id: int | None = None
    ops_phase: str = "IDLE"
    ops_context: dict[str, Any] = field(default_factory=dict)

    def add_episode(self, episode: dict[str, Any], *, keep: int = 8) -> None:
        """追加任务 episode，去重同 task_id。"""
        task_id = str(episode.get("task_id") or "")
        if task_id:
            self.episodes = [e for e in self.episodes if str(e.get("task_id") or "") != task_id]
            self.last_report_task_id = task_id
        self.episodes.append(dict(episode))
        if len(self.episodes) > keep:
            self.episodes = self.episodes[-keep:]

    def router_snapshot(
        self,
        *,
        active_task_id: str | None = None,
        queue_message: bool = False,
        last_intent_override: str | None = None,
    ) -> dict[str, Any]:
        """决策路由用的短状态快照。"""
        from harness.memory.dialog_state import build_router_snapshot

        return build_router_snapshot(
            last_intent=last_intent_override or self.last_intent,
            last_task_input=self.last_task_input,
            advice_offer_pending=self.advice_offer_pending,
            awaiting_clarify=self.awaiting_clarify,
            active_task_id=active_task_id,
            queue_message=queue_message,
            ops_phase=self.ops_phase,
        )

    def add_turn(
        self,
        role: str,
        content: str,
        *,
        intent: str | None = None,
        keep_last: int = 12,
    ) -> None:
        """
        追加一轮原文。

        不再按条数静默丢掉旧轮；过长时由 ``deep_summarize_if_needed`` 用 LLM 压缩。
        ``keep_last`` 仅保留兼容参数，无截断语义。
        """
        del keep_last  # 兼容旧调用方，避免静默截断
        item: dict[str, Any] = {"role": role, "content": content}
        if intent:
            item["intent"] = intent
        self.working.append(item)

    def add_turn_item(self, item: dict[str, Any], *, keep_last: int = 12) -> None:
        """追加完整 history 项（保留 id，供摘要水位）。"""
        del keep_last
        role = str(item.get("role") or "user")
        content = str(item.get("content") or "")
        if not content:
            return
        row: dict[str, Any] = {"role": role, "content": content}
        if item.get("id") is not None:
            row["id"] = item.get("id")
        if item.get("intent"):
            row["intent"] = item.get("intent")
        self.working.append(row)

    def add_archive(self, ref: str, meta: dict[str, Any] | None = None) -> None:
        """追加不可变归档指针。"""
        entry = {"ref": ref, **(meta or {})}
        if any(a.get("ref") == ref for a in self.archives):
            return
        self.archives.append(entry)

    def upsert_constraint(self, key: str, value: str) -> None:
        """写入或更新约束；同 key 旧值标为 inactive（可推翻）。"""
        for c in self.constraints:
            if c.key == key and c.active:
                c.active = False
        self.constraints.append(Constraint(key=key, value=value, active=True))

    def active_constraints(self) -> list[Constraint]:
        return [c for c in self.constraints if c.active]

    def compact_working(self, *, keep_last: int = 8, budget: TokenBudget | None = None) -> dict[str, Any]:
        """
        已废弃截断式压缩。

        请改用 ``harness.memory.summarize.deep_summarize_if_needed``（LLM、高水位才触发）。
        本方法保留为空操作，避免旧调用方再静默丢对话。
        """
        del keep_last, budget
        return {
            "compacted": False,
            "dropped_turns": 0,
            "summary_chars": len(self.summary),
            "skipped_reason": "use_deep_summarize_if_needed",
        }

    def build_prompt_layers(
        self,
        *,
        system: str,
        facts_text: str = "",
        question: str,
        budget: TokenBudget | None = None,
    ) -> dict[str, Any]:
        """
        按预算组装：system + constraints + facts + summary + working + question。

        Returns:
            dict: system / user / committed_tokens / truncated。
        """
        b = budget or TokenBudget()
        parts_sys = [system]
        cons = self.active_constraints()
        if cons:
            parts_sys.append(
                "[Constraints]\n" + "\n".join(f"- {c.key}: {c.value}" for c in cons)
            )
        if facts_text:
            parts_sys.append(facts_text)
        if self.episodes:
            lines = []
            for ep in self.episodes[-5:]:
                tid = ep.get("task_id") or "?"
                kind = ep.get("task_type") or ""
                text = str(ep.get("summary") or "")[:160]
                extra = []
                if ep.get("goal_mode"):
                    extra.append(str(ep.get("goal_mode")))
                if ep.get("time_window_days"):
                    extra.append(f"{ep.get('time_window_days')}d")
                suffix = f" ({', '.join(extra)})" if extra else ""
                lines.append(f"- {kind} {tid}{suffix}: {text}")
            parts_sys.append("[Episodes]\n" + "\n".join(lines))
        if self.archives:
            refs = ", ".join(a.get("ref", "") for a in self.archives[-5:])
            parts_sys.append(f"[Archives] {refs}")

        sys_text = "\n\n".join(parts_sys)
        committed = b.sized(sys_text)

        # 对话原文与摘要整段保留，不再中途截断；过长应先走 LLM 深度摘要
        ctx_chunks: list[str] = []
        if self.summary:
            ctx_chunks.append(self.summary)
        for m in self.working:
            ctx_chunks.append(f"{m.get('role')}: {m.get('content')}")
        user_body = "\n".join(ctx_chunks).strip()

        user = ""
        if user_body:
            user += "[Context]\n" + user_body + "\n\n"
        user += "[Question]\n" + question
        committed += b.sized(user)
        over_budget = committed > b.input_limit
        return {
            "system": sys_text,
            "user": user,
            "committed_tokens": committed,
            "input_limit": b.input_limit,
            "truncated": False,
            "over_budget": over_budget,
        }


class MemoryStore:
    """进程内会话记忆（正式可由 Java 持久化；此处供 Python 侧组装上下文）。"""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionMemory] = {}

    def get(self, conversation_id: str) -> SessionMemory:
        mem = self._sessions.get(conversation_id)
        if mem is None:
            mem = SessionMemory(conversation_id=conversation_id)
            self._sessions[conversation_id] = mem
        return mem
