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

from harness.memory.tokens import TokenBudget, estimate_tokens


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
    """

    conversation_id: str
    working: list[dict[str, str]] = field(default_factory=list)
    summary: str = ""
    archives: list[dict[str, Any]] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    last_intent: str | None = None
    last_task_input: dict[str, Any] = field(default_factory=dict)

    def add_turn(self, role: str, content: str, *, keep_last: int = 12) -> None:
        """追加一轮，超出 keep_last 的进入待压缩区（由 compact 处理）。"""
        self.working.append({"role": role, "content": content})
        # 软上限：留给 compact 决定
        if len(self.working) > keep_last * 2:
            self.working = self.working[-(keep_last * 2) :]

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
        确定性压缩：尾部保留，更早部分折叠进 summary（不调用 LLM）。

        Returns:
            dict: compacted / dropped_turns / summary_chars。
        """
        keep_last = max(2, keep_last)
        if len(self.working) <= keep_last:
            return {"compacted": False, "dropped_turns": 0, "summary_chars": len(self.summary)}

        old, self.working = self.working[:-keep_last], self.working[-keep_last:]
        bullets = []
        for m in old:
            role = m.get("role", "?")
            content = (m.get("content") or "").replace("\n", " ")
            bullets.append(f"- {role}: {content[:120]}")
        chunk = "\n".join(bullets)
        # 禁止对 summary 再摘要：只原文追加搬运
        if self.summary:
            self.summary = self.summary.rstrip() + "\n" + chunk
        else:
            self.summary = "[Earlier turns]\n" + chunk

        # 预算裁剪 summary 尾部优先保留（新的更重要）
        if budget is not None:
            max_sum = min(2000, budget.input_limit // 8)
            while estimate_tokens(self.summary) > max_sum and "\n" in self.summary:
                # 丢掉最旧行
                parts = self.summary.split("\n")
                self.summary = "\n".join(parts[1:])

        return {
            "compacted": True,
            "dropped_turns": len(old),
            "summary_chars": len(self.summary),
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
        if self.archives:
            refs = ", ".join(a.get("ref", "") for a in self.archives[-5:])
            parts_sys.append(f"[Archives] {refs}")

        sys_text = "\n\n".join(parts_sys)
        committed = b.sized(sys_text)

        # working + summary 填入 user 侧上下文
        ctx_chunks: list[str] = []
        if self.summary:
            ctx_chunks.append(self.summary)
        for m in self.working:
            ctx_chunks.append(f"{m.get('role')}: {m.get('content')}")

        user_body = ""
        truncated = False
        for chunk in ctx_chunks:
            trial = (user_body + "\n" + chunk).strip()
            need = b.sized(trial) + b.sized(question) + 64
            if committed + need > b.input_limit:
                truncated = True
                break
            user_body = trial

        user = ""
        if user_body:
            user += "[Context]\n" + user_body + "\n\n"
        user += "[Question]\n" + question
        committed += b.sized(user)
        return {
            "system": sys_text,
            "user": user,
            "committed_tokens": committed,
            "input_limit": b.input_limit,
            "truncated": truncated,
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
