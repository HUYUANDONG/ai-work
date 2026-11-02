"""
报告读写 Tool。

先 upsert 报告再 complete；对话追问只读已落库报告。
"""

from typing import Any

from harness.runtime import AppRuntime


async def upsert_explosion_report(
    runtime: AppRuntime,
    task_id: str,
    report: dict[str, Any],
) -> None:
    """
    写入爆品报告。

    Args:
        runtime: AppRuntime。
        task_id: 任务 ID。
        report: 报告体。
    """
    await runtime.java_client.upsert_explosion_report(task_id, report)


async def upsert_quality_report(
    runtime: AppRuntime,
    task_id: str,
    report: dict[str, Any],
) -> None:
    """
    写入质检报告。

    Args:
        runtime: AppRuntime。
        task_id: 任务 ID。
        report: 报告体。
    """
    await runtime.java_client.upsert_quality_report(task_id, report)


async def get_conversation_reports(
    runtime: AppRuntime,
    conversation_id: str,
    *,
    user_id: str,
    limit: int = 3,
) -> dict[str, Any]:
    """
    对话 Agent 只读本会话报告。

    Args:
        runtime: AppRuntime。
        conversation_id: 会话 ID。
        user_id: 当前用户。
        limit: 条数上限。

    Returns:
        dict[str, Any]: 报告列表。
    """
    return await runtime.java_client.get_conversation_reports(
        conversation_id,
        user_id=user_id,
        limit=limit,
    )
