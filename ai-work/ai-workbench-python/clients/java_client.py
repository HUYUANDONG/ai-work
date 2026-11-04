"""
Workbench Service 内部 HTTP 客户端。

``mock_features=True`` 时全部走本地 fixture / 内存队列，无需 Java。
正式环境走真实 HTTP；HMAC 本期不做，仅带 ``X-Workbench-Caller: python``。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from harness.resilience import (
    SlidingWindowCircuitBreaker,
    call_with_retry,
    http_status_is_transient,
    is_transient_http_error,
)

logger = logging.getLogger(__name__)

WORKFLOW_VERSION = "explosion-quality-1.0.0"


class JavaClient:
    """
    调用 ai-workbench-service 内部 API。

    Attributes:
        base_url: Service 内网 Base URL。
        mock_features: True 时不访问网络。
        timeout: HTTP 超时秒。
        max_attempts: 瞬时故障总尝试次数（含首次）。
        breaker: 滑动窗口熔断器（仅真实 HTTP）。
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080",
        *,
        mock_features: bool = True,
        timeout: float = 30.0,
        max_attempts: int = 2,
        breaker: SlidingWindowCircuitBreaker | None = None,
    ) -> None:
        """
        Args:
            base_url: Java Service Base URL。
            mock_features: 是否本地 mock。
            timeout: 请求超时。
            max_attempts: 瞬时故障总尝试次数。
            breaker: 可选熔断器。
        """
        self.base_url = base_url.rstrip("/")
        self.mock_features = mock_features
        self.timeout = timeout
        self.max_attempts = max(1, max_attempts)
        self.breaker = breaker or SlidingWindowCircuitBreaker(name="java-http")
        # mock 状态
        self._mock_task_queue: list[dict[str, Any]] = []
        self._mock_reports_by_conversation: dict[str, list[dict[str, Any]]] = {}
        self._mock_completed: list[dict[str, Any]] = []
        self._mock_failed: list[dict[str, Any]] = []
        # task_id → 控制位与思考事件、追问队列
        self._mock_task_control: dict[str, dict[str, Any]] = {}
        self._mock_progress: dict[str, list[dict[str, Any]]] = {}
        self._mock_message_queue: dict[str, list[dict[str, Any]]] = {}

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Workbench-Caller": "python",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """
        真实 HTTP；瞬时 429/5xx 与连接错误走退避重试，并计入熔断窗口。

        超时不重试。4xx（非 429）视为服务可达，记成功。
        """
        url = f"{self.base_url}{path}"

        async def _once() -> httpx.Response:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                resp = await client.request(
                    method,
                    url,
                    headers=self._headers(),
                    json=json_body,
                    params=params,
                )
            if http_status_is_transient(resp.status_code):
                # 让 call_with_retry 记失败并决定是否再试
                raise httpx.HTTPStatusError(
                    f"transient HTTP {resp.status_code}",
                    request=resp.request,
                    response=resp,
                )
            return resp

        try:
            return await call_with_retry(
                _once,
                max_attempts=self.max_attempts,
                breaker=self.breaker,
                is_retryable=is_transient_http_error,
                label=f"java.{method} {path}",
            )
        except httpx.HTTPStatusError as exc:
            # 重试用尽：仍把最后一次响应交给上层 raise_for_status
            return exc.response

    # ----- features -----

    async def query_features(self, body: dict[str, Any]) -> dict[str, Any]:
        """
        批量查询快照特征（``POST /internal/features/query``）。

        Args:
            body: 查询条件。

        Returns:
            dict: snapshot_date / row_count / items。
        """
        if self.mock_features:
            return self._load_mock_features(body)

        resp = await self._request("POST", "/internal/features/query", json_body=body)
        resp.raise_for_status()
        data = resp.json()
        data.setdefault("mock", data.get("source") == "fixture")
        return data

    async def query_advise(self, body: dict[str, Any]) -> dict[str, Any]:
        """
        建议补数（``POST /internal/features/advise``）。

        Args:
            body: user_id / sku_ids / days。

        Returns:
            dict: plates / store / source。
        """
        if self.mock_features:
            return {
                "sku_ids": list(body.get("sku_ids") or []),
                "plates": [
                    {
                        "stat_field": "mock-home",
                        "stat_field_name": "首页爆款位",
                        "self_pv": 1200,
                        "self_uv": 480,
                        "order_sales": 3200,
                        "order_numbers": 18,
                    },
                    {
                        "stat_field": "mock-act",
                        "stat_field_name": "活动坑位",
                        "self_pv": 800,
                        "self_uv": 260,
                        "order_sales": 1500,
                        "order_numbers": 9,
                    },
                ],
                "store": {
                    "total_sales": 50000,
                    "order_numbers": 120,
                    "hpage_uv": 8000,
                    "conversion_rate": 1.5,
                },
                "source": "fixture",
                "mock": True,
            }
        resp = await self._request("POST", "/internal/features/advise", json_body=body)
        resp.raise_for_status()
        return resp.json()

    async def get_product_features(
        self,
        sku_id: str,
        *,
        stat_date: str | None = None,
    ) -> dict[str, Any]:
        """
        单品特征（``GET /internal/products/{skuId}/features``）。

        Args:
            sku_id: SKU。
            stat_date: 可选统计日。

        Returns:
            dict: snapshot_date / item。

        Raises:
            LookupError: 找不到 SKU。
        """
        if self.mock_features:
            raw = self._load_mock_features({"sku_ids": [sku_id], "on_sale_only": False})
            items = raw.get("items") or []
            if not items:
                raise LookupError(f"sku not found: {sku_id}")
            return {
                "snapshot_date": raw.get("snapshot_date"),
                "item": items[0],
                "mock": True,
            }

        params = {}
        if stat_date:
            params["stat_date"] = stat_date
        resp = await self._request(
            "GET",
            f"/internal/products/{sku_id}/features",
            params=params or None,
        )
        if resp.status_code == 404:
            raise LookupError(f"sku not found: {sku_id}")
        resp.raise_for_status()
        data = resp.json()
        data.setdefault("mock", False)
        return data

    async def get_product_detail(self, sku_id: str) -> dict[str, Any]:
        """
        商品详情（正式接口未就绪时 mock）。

        Args:
            sku_id: SKU。

        Returns:
            dict: title / selling_points / specs / mock。
        """
        sid = str(sku_id)
        if self.mock_features:
            try:
                feat = await self.get_product_features(sid)
                item = dict(feat.get("item") or {})
            except LookupError:
                item = {"sku_id": sid, "title": f"商品-{sid}"}
            title = str(item.get("title") or item.get("goodsName") or f"商品-{sid}")
            return {
                "sku_id": sid,
                "title": title,
                "selling_points": [
                    "店铺主推款",
                    f"近窗销量信号见特征（orderSales={item.get('orderSales')}）",
                    "支持七天无理由（mock）",
                ],
                "specs": {
                    "brand": item.get("brand") or item.get("gbName") or "未知品牌",
                    "price": item.get("price"),
                    "cost": item.get("cost"),
                },
                "mock": True,
                "source": "fixture",
            }
        resp = await self._request("GET", f"/internal/products/{sid}/detail")
        if resp.status_code == 404:
            raise LookupError(f"sku not found: {sid}")
        resp.raise_for_status()
        data = resp.json()
        data.setdefault("mock", False)
        return data

    async def get_product_reviews(
        self,
        sku_id: str,
        *,
        limit: int = 5,
    ) -> dict[str, Any]:
        """
        商品评论（正式接口未就绪时 mock）。

        Args:
            sku_id: SKU。
            limit: 条数上限。

        Returns:
            dict: reviews[] / mock。
        """
        sid = str(sku_id)
        n = max(1, min(int(limit), 20))
        if self.mock_features:
            reviews = [
                {
                    "review_id": f"r-{sid}-{i}",
                    "rating": 5 if i % 3 else 4,
                    "content": (
                        "质量不错，物流快，会回购。"
                        if i % 2 == 0
                        else "包装扎实，色差可接受，性价比高。"
                    ),
                    "created_at": "2026-10-01",
                }
                for i in range(1, n + 1)
            ]
            return {"sku_id": sid, "reviews": reviews, "mock": True, "source": "fixture"}
        resp = await self._request(
            "GET",
            f"/internal/products/{sid}/reviews",
            params={"limit": n},
        )
        resp.raise_for_status()
        data = resp.json()
        data.setdefault("mock", False)
        return data

    async def get_inventory_policy(
        self,
        sku_ids: list[str],
    ) -> dict[str, Any]:
        """
        库存预警与限购策略（正式接口未就绪时 mock）。

        Args:
            sku_ids: SKU 列表。

        Returns:
            dict: items[] 含 stock_qty / warning / purchase_limit。
        """
        ids = [str(x) for x in (sku_ids or [])[:50]]
        if self.mock_features:
            items: list[dict[str, Any]] = []
            for i, sid in enumerate(ids):
                stock = 8 if i % 3 == 0 else (120 if i % 3 == 1 else 45)
                warning = "LOW_STOCK" if stock < 20 else ("OVERSTOCK" if stock > 100 else "OK")
                purchase_limit = 2 if stock < 20 else (0 if stock > 100 else 5)
                items.append(
                    {
                        "sku_id": sid,
                        "stock_qty": stock,
                        "warning": warning,
                        "purchase_limit": purchase_limit,
                        "rationale": (
                            "库存紧张，建议限购并补货"
                            if warning == "LOW_STOCK"
                            else (
                                "库存偏高，建议控投清仓"
                                if warning == "OVERSTOCK"
                                else "库存健康"
                            )
                        ),
                    }
                )
            return {"items": items, "mock": True, "source": "fixture"}
        resp = await self._request(
            "POST",
            "/internal/inventory/policy",
            json_body={"sku_ids": ids},
        )
        resp.raise_for_status()
        data = resp.json()
        data.setdefault("mock", False)
        return data

    def _load_mock_features(self, body: dict[str, Any]) -> dict[str, Any]:
        """从 fixtures 加载并过滤。"""
        path = Path(__file__).resolve().parents[1] / "fixtures" / "mock_features.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        items: list[dict[str, Any]] = list(raw.get("items") or [])

        if body.get("on_sale_only", True):
            items = [x for x in items if x.get("on_sale") is True]

        category_id = body.get("category_id")
        if category_id:
            items = [x for x in items if x.get("category_id") == category_id]

        sku_ids = body.get("sku_ids")
        if sku_ids:
            allow = set(sku_ids)
            items = [x for x in items if x.get("sku_id") in allow]

        return {
            "snapshot_date": raw.get("snapshot_date"),
            "row_count": len(items),
            "items": items,
            "mock": True,
            "query": body,
        }

    # ----- reports -----

    async def upsert_explosion_report(self, task_id: str, report: dict[str, Any]) -> None:
        """爆品报告 upsert。"""
        if self.mock_features:
            self._mock_store_report(task_id, "EXPLOSION", report)
            return
        resp = await self._request(
            "PUT",
            f"/internal/tasks/{task_id}/explosion-report",
            json_body=report,
        )
        resp.raise_for_status()

    async def upsert_quality_report(self, task_id: str, report: dict[str, Any]) -> None:
        """质检报告 upsert。"""
        if self.mock_features:
            self._mock_store_report(task_id, "QUALITY", report)
            return
        resp = await self._request(
            "PUT",
            f"/internal/tasks/{task_id}/quality-report",
            json_body=report,
        )
        resp.raise_for_status()

    def _mock_store_report(
        self,
        task_id: str,
        task_type: str,
        report: dict[str, Any],
    ) -> None:
        header = dict(report.get("header") or {})
        header.setdefault("task_id", task_id)
        conversation_id = str(header.get("conversation_id") or "mock-conversation")
        entry = {
            "task_id": task_id,
            "task_type": task_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "header": header,
            "items": list(report.get("items") or []),
        }
        bucket = self._mock_reports_by_conversation.setdefault(conversation_id, [])
        bucket.insert(0, entry)
        # 也挂一份到 default，方便无 conversation 时追问
        if conversation_id != "mock-conversation":
            self._mock_reports_by_conversation.setdefault("mock-conversation", []).insert(
                0, entry
            )

    async def get_conversation_reports(
        self,
        conversation_id: str,
        *,
        user_id: str,
        limit: int = 3,
    ) -> dict[str, Any]:
        """读取本会话最近报告。"""
        if self.mock_features:
            _ = user_id
            reports = list(self._mock_reports_by_conversation.get(conversation_id) or [])
            return {
                "conversation_id": conversation_id,
                "reports": reports[: max(1, limit)],
                "mock": True,
            }

        resp = await self._request(
            "GET",
            f"/internal/conversations/{conversation_id}/reports",
            params={"user_id": user_id, "limit": limit},
        )
        resp.raise_for_status()
        data = resp.json()
        data.setdefault("mock", False)
        return data

    # ----- tasks -----

    def enqueue_mock_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        本地入队（仅 mock），供 Worker claim。

        Args:
            task: 至少含 task_type / input；可缺 task_id。

        Returns:
            dict: 入队后的完整任务。
        """
        if not self.mock_features:
            raise RuntimeError("enqueue_mock_task only available in mock mode")
        payload = {
            "task_id": task.get("task_id") or f"mock-{uuid4().hex[:12]}",
            "run_id": task.get("run_id") or f"run-{uuid4().hex[:8]}",
            "task_type": str(task.get("task_type", "EXPLOSION")).upper(),
            "lease_token": task.get("lease_token") or f"lease-{uuid4().hex[:8]}",
            "lease_seconds": int(task.get("lease_seconds") or 60),
            "conversation_id": task.get("conversation_id") or "mock-conversation",
            "user_id": task.get("user_id") or "mock-user",
            "input": dict(task.get("input") or {}),
        }
        self._mock_task_queue.append(payload)
        self._mock_ctrl(str(payload["task_id"]))
        return payload

    async def claim_task(
        self,
        *,
        task_types: list[str],
        workflow_version: str,
        worker_id: str = "py-worker",
    ) -> dict[str, Any] | None:
        """领取一条可执行任务；无任务返回 None。"""
        if self.mock_features:
            allow = {t.upper() for t in task_types}
            for i, t in enumerate(self._mock_task_queue):
                if t.get("task_type") in allow:
                    return self._mock_task_queue.pop(i)
            return None

        resp = await self._request(
            "POST",
            "/internal/tasks/claim",
            json_body={
                "task_types": task_types,
                "workflow_version": workflow_version or WORKFLOW_VERSION,
                "worker_id": worker_id,
            },
        )
        if resp.status_code == 204 or not resp.content:
            return None
        resp.raise_for_status()
        data = resp.json()
        if data is None:
            return None
        return data

    def _mock_ctrl(self, task_id: str) -> dict[str, Any]:
        return self._mock_task_control.setdefault(
            task_id,
            {
                "cancel_requested": False,
                "cancel_reason": "",
                "pause_requested": False,
                "pause_reason": "",
            },
        )

    def mock_request_cancel(self, task_id: str, reason: str = "用户取消") -> None:
        """联调：标记取消（正式由 Java 写 cancel_requested_at）。"""
        ctrl = self._mock_ctrl(task_id)
        ctrl["cancel_requested"] = True
        ctrl["cancel_reason"] = reason

    def mock_request_pause(self, task_id: str, reason: str = "用户暂停") -> None:
        """联调：标记暂停。"""
        ctrl = self._mock_ctrl(task_id)
        ctrl["pause_requested"] = True
        ctrl["pause_reason"] = reason

    async def request_task_control(
        self,
        task_id: str,
        *,
        action: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """
        暂停 / 取消 / 继续。

        ``POST /internal/tasks/{taskId}/control``
        """
        act = (action or "").strip().lower()
        if self.mock_features:
            if act == "pause":
                self.mock_request_pause(task_id, reason or "用户暂停")
            elif act == "cancel":
                self.mock_request_cancel(task_id, reason or "用户取消")
            elif act in {"resume", "continue"}:
                return {"ok": True, "action": "resume", "task_id": task_id, "mock": True}
            return {"ok": True, "action": act, "task_id": task_id, "mock": True}
        resp = await self._request(
            "POST",
            f"/internal/tasks/{task_id}/control",
            json_body={"action": act, "reason": reason or ""},
        )
        resp.raise_for_status()
        if not resp.content:
            return {"ok": True, "action": act, "task_id": task_id}
        data = resp.json()
        return data if isinstance(data, dict) else {"ok": True, "action": act}

    def mock_enqueue_user_message(
        self,
        conversation_id: str,
        message: dict[str, Any],
    ) -> int:
        """联调：任务进行中的用户追问入队。返回队列深度。"""
        q = self._mock_message_queue.setdefault(conversation_id, [])
        q.append(message)
        return len(q)

    def mock_queue_depth(self, conversation_id: str) -> int:
        return len(self._mock_message_queue.get(conversation_id) or [])

    async def post_task_progress(
        self,
        task_id: str,
        *,
        lease_token: str,
        event: dict[str, Any],
    ) -> None:
        """
        上报思考/进度事件（Java 再 SSE 给前端）。

        ``POST /internal/tasks/{taskId}/progress``
        """
        if self.mock_features:
            bucket = self._mock_progress.setdefault(task_id, [])
            bucket.append({"lease_token": lease_token, **event})
            return
        resp = await self._request(
            "POST",
            f"/internal/tasks/{task_id}/progress",
            json_body={"lease_token": lease_token, "event": event},
        )
        resp.raise_for_status()

    def get_mock_progress(self, task_id: str) -> list[dict[str, Any]]:
        """读取 mock 思考事件。"""
        return list(self._mock_progress.get(task_id) or [])

    async def heartbeat(
        self,
        task_id: str,
        *,
        lease_token: str,
        progress: str = "",
    ) -> dict[str, Any]:
        """
        任务心跳；响应带协作式取消/暂停与排队深度。

        Returns:
            dict: cancel_requested / pause_requested / queue_depth 等。
        """
        if self.mock_features:
            ctrl = dict(self._mock_ctrl(task_id))
            # 从已入队任务上取 conversation 估排队（mock 简化）
            ctrl["progress"] = progress
            ctrl["queue_depth"] = 0
            for cid, q in self._mock_message_queue.items():
                _ = cid
                ctrl["queue_depth"] = max(ctrl["queue_depth"], len(q))
            return ctrl

        resp = await self._request(
            "POST",
            f"/internal/tasks/{task_id}/heartbeat",
            json_body={"lease_token": lease_token, "progress": progress},
        )
        resp.raise_for_status()
        if not resp.content:
            return {}
        data = resp.json()
        return data if isinstance(data, dict) else {}

    async def complete_task(
        self,
        task_id: str,
        *,
        lease_token: str,
        summary: str = "",
        result_meta: dict[str, Any] | None = None,
    ) -> None:
        """任务成功。"""
        body = {
            "lease_token": lease_token,
            "summary": summary,
            "result_meta": result_meta or {},
        }
        if self.mock_features:
            self._mock_completed.append({"task_id": task_id, **body})
            return
        resp = await self._request(
            "POST",
            f"/internal/tasks/{task_id}/complete",
            json_body=body,
        )
        resp.raise_for_status()

    async def fail_task(
        self,
        task_id: str,
        *,
        lease_token: str,
        error_code: str,
        message: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """
        任务失败 / 暂停 / 取消。

        Args:
            task_id: 任务 ID。
            lease_token: 租约。
            error_code: 错误码。
            message: 说明。
            extra: 合并进 fail body（如 graph_thread_id / paused_at）。
        """
        body: dict[str, Any] = {
            "lease_token": lease_token,
            "error_code": error_code,
            "message": message,
        }
        if extra:
            for key, value in extra.items():
                if key in body or value is None:
                    continue
                body[key] = value
        if self.mock_features:
            self._mock_failed.append({"task_id": task_id, **body})
            return
        resp = await self._request(
            "POST",
            f"/internal/tasks/{task_id}/fail",
            json_body=body,
        )
        resp.raise_for_status()

