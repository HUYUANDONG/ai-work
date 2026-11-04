package cn.aiworkbench.service.internalapi.task;

import cn.aiworkbench.service.conversation.sse.ConversationSseHub;
import cn.aiworkbench.service.internalapi.support.InternalApiException;
import cn.aiworkbench.service.persist.TaskPersistService;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;

/**
 * 任务运行时。MySQL 开启时以 {@code ai_task} 为队列权威（SKIP LOCKED 领取）；
 * 未开库时退回进程内存（单测 / 无库联调）。
 */
@Component
public class InMemoryTaskRuntime {

    private final ConversationSseHub sseHub;
    private final ObjectProvider<TaskPersistService> persistProvider;

    /**
     * 测试用：不落库。
     *
     * @param sseHub 会话推送
     */
    public InMemoryTaskRuntime(ConversationSseHub sseHub) {
        this(sseHub, new ObjectProvider<>() {
            @Override
            public TaskPersistService getObject() {
                return null;
            }

            @Override
            public TaskPersistService getObject(Object... args) {
                return null;
            }

            @Override
            public TaskPersistService getIfAvailable() {
                return null;
            }

            @Override
            public TaskPersistService getIfUnique() {
                return null;
            }
        });
    }

    /**
     * @param sseHub          会话推送
     * @param persistProvider 可选 MySQL 队列权威
     */
    @Autowired
    public InMemoryTaskRuntime(
            ConversationSseHub sseHub,
            ObjectProvider<TaskPersistService> persistProvider) {
        this.sseHub = sseHub;
        this.persistProvider = persistProvider;
    }

    private final Deque<Map<String, Object>> queue = new ArrayDeque<>();
    private final Map<String, Map<String, Object>> leased = new ConcurrentHashMap<>();
    private final Map<String, Map<String, Object>> finished = new ConcurrentHashMap<>();
    private final Map<String, Map<String, Object>> control = new ConcurrentHashMap<>();
    private final Map<String, List<Map<String, Object>>> progress = new ConcurrentHashMap<>();
    private final Map<String, List<Map<String, Object>>> messageQueue = new ConcurrentHashMap<>();
    private final Object finishedLock = new Object();

    /**
     * 入队一条可领取任务（对话 need_task 或联调入队）。
     *
     * @param body 任务草稿
     * @return 入队后的完整任务
     */
    public synchronized Map<String, Object> enqueue(Map<String, Object> body) {
        Map<String, Object> task = new LinkedHashMap<>();
        String taskId = stringOr(body.get("task_id"), "t-" + UUID.randomUUID().toString().replace("-", "").substring(0, 12));
        task.put("task_id", taskId);
        task.put("run_id", stringOr(body.get("run_id"), "r-" + UUID.randomUUID().toString().replace("-", "").substring(0, 8)));
        task.put("task_type", String.valueOf(body.getOrDefault("task_type", "EXPLOSION")).toUpperCase());
        task.put("lease_token", stringOr(body.get("lease_token"), "lease-" + UUID.randomUUID().toString().replace("-", "").substring(0, 8)));
        task.put("lease_seconds", body.get("lease_seconds") instanceof Number n ? n.intValue() : 60);
        task.put("conversation_id", stringOr(body.get("conversation_id"), "c-unknown"));
        task.put("user_id", stringOr(body.get("user_id"), "u-unknown"));
        Object input = body.get("input");
        Map<String, Object> inputMap = input instanceof Map<?, ?> m
                ? new LinkedHashMap<>(castMap(m))
                : new LinkedHashMap<>();
        // LangGraph thread_id：首跑默认用 task_id；续跑必须带上原 graph_thread_id
        Object existingThread = inputMap.get("graph_thread_id");
        if (existingThread == null || String.valueOf(existingThread).isBlank()) {
            inputMap.put("graph_thread_id", taskId);
        }
        task.put("input", inputMap);
        TaskPersistService db = persist();
        if (db != null) {
            db.onEnqueue(task);
            return new LinkedHashMap<>(task);
        }
        queue.addLast(task);
        control.put(taskId, defaultControl());
        return new LinkedHashMap<>(task);
    }

    /**
     * 领取一条匹配类型的任务。
     *
     * @param taskTypes        可领取类型
     * @param workflowVersion  工作流版本
     * @param workerId         Worker 标识
     * @return 任务或 empty
     */
    public synchronized Optional<Map<String, Object>> claim(
            List<String> taskTypes, String workflowVersion, String workerId) {
        if (taskTypes == null || taskTypes.isEmpty()) {
            throw InternalApiException.badRequest("task_types 不能为空");
        }
        var allow = taskTypes.stream().map(t -> t == null ? "" : t.toUpperCase()).toList();
        TaskPersistService db = persist();
        if (db != null) {
            Optional<Map<String, Object>> claimed = db.claim(allow, workflowVersion, workerId);
            claimed.ifPresent(task -> leased.put(String.valueOf(task.get("task_id")), new LinkedHashMap<>(task)));
            return claimed.map(LinkedHashMap::new);
        }
        for (var it = queue.iterator(); it.hasNext(); ) {
            Map<String, Object> task = it.next();
            String type = String.valueOf(task.get("task_type"));
            if (!allow.contains(type)) {
                continue;
            }
            it.remove();
            task.put("claimed_at", Instant.now().toString());
            task.put("worker_id", workerId);
            task.put("workflow_version", workflowVersion);
            leased.put(String.valueOf(task.get("task_id")), new LinkedHashMap<>(task));
            control.computeIfAbsent(String.valueOf(task.get("task_id")), id -> defaultControl());
            return Optional.of(new LinkedHashMap<>(task));
        }
        return Optional.empty();
    }

    /**
     * 上报思考进度。
     *
     * @param taskId     任务 ID
     * @param leaseToken 租约
     * @param event      事件
     */
    public void postProgress(String taskId, String leaseToken, Map<String, Object> event) {
        Map<String, Object> task = assertLease(taskId, leaseToken);
        Map<String, Object> safe = event == null ? Map.of() : new LinkedHashMap<>(event);
        progress.computeIfAbsent(taskId, id -> new ArrayList<>()).add(safe);
        String conversationId = String.valueOf(task.getOrDefault("conversation_id", "c-unknown"));
        String stage = String.valueOf(safe.getOrDefault("stage", ""));
        if ("llm_delta".equals(stage)) {
            Object delta = safe.get("detail");
            if (delta == null && safe.get("data") instanceof Map<?, ?> data) {
                delta = data.get("delta");
            }
            sseHub.publish(conversationId, "llm_delta", Map.of(
                    "task_id", taskId,
                    "delta", delta == null ? "" : String.valueOf(delta)
            ));
            return;
        }
        if (Boolean.FALSE.equals(safe.get("visible"))) {
            return;
        }
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("task_id", taskId);
        payload.put("stage", stage);
        payload.put("title", safe.getOrDefault("title", ""));
        payload.put("detail", safe.getOrDefault("detail", ""));
        payload.put("seq", safe.get("seq"));
        sseHub.publish(conversationId, "thinking", payload);
    }

    /**
     * 心跳，返回取消/暂停与排队深度。
     *
     * @param taskId     任务 ID
     * @param leaseToken 租约
     * @param progressText 进度文案
     * @return 控制位
     */
    public Map<String, Object> heartbeat(String taskId, String leaseToken, String progressText) {
        Map<String, Object> task = assertLease(taskId, leaseToken);
        String conversationId = String.valueOf(task.get("conversation_id"));
        Map<String, Object> ctrl;
        TaskPersistService db = persist();
        if (db != null) {
            ctrl = new LinkedHashMap<>(db.heartbeat(taskId, leaseToken));
        } else {
            ctrl = new LinkedHashMap<>(control.computeIfAbsent(taskId, id -> defaultControl()));
        }
        ctrl.put("progress", progressText == null ? "" : progressText);
        ctrl.put("queue_depth", messageQueue.getOrDefault(conversationId, List.of()).size());
        return ctrl;
    }

    /**
     * 完成任务。
     *
     * @param taskId     任务 ID
     * @param leaseToken 租约
     * @param body       完成载荷
     */
    public void complete(String taskId, String leaseToken, Map<String, Object> body) {
        Map<String, Object> task = assertLease(taskId, leaseToken);
        leased.remove(taskId);
        Map<String, Object> done = new LinkedHashMap<>(task);
        done.put("task_id", taskId);
        done.put("status", "COMPLETED");
        done.put("complete_body", body == null ? Map.of() : new LinkedHashMap<>(body));
        finished.put(taskId, done);
        String conversationId = String.valueOf(task.getOrDefault("conversation_id", "c-unknown"));
        Object summary = body == null ? null : body.get("summary");
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("task_id", taskId);
        payload.put("status", "COMPLETED");
        if (summary != null) {
            payload.put("summary", String.valueOf(summary));
        }
        sseHub.publish(conversationId, "task_done", payload);
        persistRequired(p -> p.onComplete(done, body == null ? Map.of() : body));
        signalFinished();
    }

    /**
     * 失败任务。
     *
     * @param taskId     任务 ID
     * @param leaseToken 租约
     * @param body       失败载荷
     */
    public void fail(String taskId, String leaseToken, Map<String, Object> body) {
        Map<String, Object> task = assertLease(taskId, leaseToken);
        leased.remove(taskId);
        Map<String, Object> failBody = body == null ? Map.of() : new LinkedHashMap<>(body);
        String errorCode = String.valueOf(failBody.getOrDefault("error_code", "FAILED"));
        String status = switch (errorCode) {
            case "PAUSED" -> "PAUSED";
            case "CANCELLED" -> "CANCELLED";
            default -> "FAILED";
        };
        Map<String, Object> done = new LinkedHashMap<>(task);
        done.put("task_id", taskId);
        done.put("status", status);
        done.put("fail_body", failBody);
        finished.put(taskId, done);
        String conversationId = String.valueOf(task.getOrDefault("conversation_id", "c-unknown"));
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("task_id", taskId);
        payload.put("status", status);
        payload.put("error_code", errorCode);
        payload.put("summary", String.valueOf(failBody.getOrDefault("message", failBody.getOrDefault("summary", ""))));
        sseHub.publish(conversationId, "task_done", payload);
        persistRequired(p -> p.onFail(done, status, failBody));
        signalFinished();
    }

    /**
     * 标记取消（前端/Java 侧写入）。
     *
     * @param taskId 任务 ID
     * @param reason 原因
     */
    public void requestCancel(String taskId, String reason) {
        if (!isRunning(taskId) && findLeased(taskId).isEmpty()) {
            throw InternalApiException.notFound("task not running: " + taskId);
        }
        Map<String, Object> ctrl = control.computeIfAbsent(taskId, id -> defaultControl());
        ctrl.put("cancel_requested", true);
        ctrl.put("cancel_reason", reason == null ? "" : reason);
        ctrl.put("pause_requested", false);
        persistRequired(p -> p.onCancelRequested(taskId, reason));
        publishControl(taskId, "cancel", reason);
    }

    /**
     * 标记暂停。
     *
     * @param taskId 任务 ID
     * @param reason 原因
     */
    public void requestPause(String taskId, String reason) {
        if (!isRunning(taskId) && findLeased(taskId).isEmpty()) {
            throw InternalApiException.notFound("task not running: " + taskId);
        }
        Map<String, Object> ctrl = control.computeIfAbsent(taskId, id -> defaultControl());
        ctrl.put("pause_requested", true);
        ctrl.put("pause_reason", reason == null ? "" : reason);
        persistRequired(p -> p.onPauseRequested(taskId, reason));
        publishControl(taskId, "pause", reason);
    }

    /**
     * 从 PAUSED 终态续跑：新 task_id 领租约，但复用 LangGraph {@code graph_thread_id} 断点。
     *
     * @param taskId 已暂停任务
     * @return 新任务
     */
    public Map<String, Object> resumePaused(String taskId) {
        Map<String, Object> done = findFinished(taskId).orElse(null);
        if (done == null) {
            throw InternalApiException.notFound("task not finished: " + taskId);
        }
        if (!"PAUSED".equals(String.valueOf(done.get("status")))) {
            throw InternalApiException.conflict("仅 PAUSED 任务可继续，当前=" + done.get("status"));
        }
        Map<String, Object> prevInput = done.get("input") instanceof Map<?, ?> m
                ? new LinkedHashMap<>(castMap(m))
                : new LinkedHashMap<>();
        Map<String, Object> failBody = done.get("fail_body") instanceof Map<?, ?> fb
                ? castMap(fb)
                : Map.of();
        String graphThreadId = firstNonBlank(
                failBody.get("graph_thread_id"),
                prevInput.get("graph_thread_id"),
                taskId);
        Map<String, Object> nextInput = new LinkedHashMap<>(prevInput);
        nextInput.put("graph_thread_id", graphThreadId);
        nextInput.put("resume_from_checkpoint", true);
        nextInput.put("resumed_from_task_id", taskId);
        Object pausedAt = failBody.get("paused_at");
        if (pausedAt != null && !String.valueOf(pausedAt).isBlank()) {
            nextInput.put("resume_after", String.valueOf(pausedAt));
        }

        Map<String, Object> draft = new LinkedHashMap<>();
        draft.put("task_type", done.get("task_type"));
        draft.put("conversation_id", done.get("conversation_id"));
        draft.put("user_id", done.get("user_id"));
        draft.put("run_id", done.get("run_id"));
        draft.put("input", nextInput);
        Map<String, Object> created = enqueue(draft);
        String conversationId = String.valueOf(done.getOrDefault("conversation_id", "c-unknown"));
        sseHub.publish(conversationId, "thinking", Map.of(
                "stage", "task_resumed",
                "title", "已从断点继续分析…",
                "detail", "thread=" + graphThreadId + " task_id=" + created.get("task_id"),
                "task_id", String.valueOf(created.get("task_id")),
                "graph_thread_id", graphThreadId,
                "resumed_from", taskId
        ));
        return created;
    }

    private static String firstNonBlank(Object... values) {
        if (values == null) {
            return "";
        }
        for (Object value : values) {
            if (value == null) {
                continue;
            }
            String text = String.valueOf(value).trim();
            if (!text.isEmpty() && !"null".equalsIgnoreCase(text)) {
                return text;
            }
        }
        return "";
    }

    /**
     * 控制事件推给会话 SSE。
     *
     * @param taskId 任务
     * @param action pause/cancel
     * @param reason 原因
     */
    private void publishControl(String taskId, String action, String reason) {
        Map<String, Object> task = findLeased(taskId).orElse(null);
        if (task == null) {
            TaskPersistService db = persist();
            if (db != null) {
                task = db.loadRunning(taskId).orElse(null);
            }
        }
        if (task == null) {
            synchronized (this) {
                for (Map<String, Object> item : queue) {
                    if (taskId.equals(String.valueOf(item.get("task_id")))) {
                        task = item;
                        break;
                    }
                }
            }
        }
        if (task == null) {
            return;
        }
        String conversationId = String.valueOf(task.getOrDefault("conversation_id", "c-unknown"));
        sseHub.publish(conversationId, "thinking", Map.of(
                "stage", "control_" + action,
                "title", "pause".equals(action) ? "已请求暂停…" : "已请求取消…",
                "detail", reason == null ? "" : reason,
                "task_id", taskId,
                "control", action
        ));
    }

    /**
     * 追问入队。
     *
     * @param conversationId 会话
     * @param message        消息
     * @return 队列深度
     */
    public int enqueueUserMessage(String conversationId, Map<String, Object> message) {
        List<Map<String, Object>> q = messageQueue.computeIfAbsent(conversationId, id -> new ArrayList<>());
        q.add(message == null ? Map.of() : new LinkedHashMap<>(message));
        return q.size();
    }

    /**
     * 查找已领取任务（供报告绑定会话）。
     *
     * @param taskId 任务 ID
     * @return 任务
     */
    public Optional<Map<String, Object>> findLeased(String taskId) {
        Map<String, Object> task = leased.get(taskId);
        if (task != null) {
            return Optional.of(new LinkedHashMap<>(task));
        }
        TaskPersistService db = persist();
        if (db != null) {
            return db.loadLeased(taskId, null);
        }
        return Optional.empty();
    }

    /**
     * 查找已完成/失败任务。
     *
     * @param taskId 任务 ID
     * @return 终态任务
     */
    public Optional<Map<String, Object>> findFinished(String taskId) {
        Map<String, Object> task = finished.get(taskId);
        if (task != null) {
            return Optional.of(new LinkedHashMap<>(task));
        }
        TaskPersistService db = persist();
        if (db != null) {
            return db.loadFinished(taskId);
        }
        return Optional.empty();
    }

    /**
     * 任务是否仍在队列或已领取未结束。
     *
     * @param taskId 任务 ID
     * @return true 表示还在跑
     */
    public boolean isRunning(String taskId) {
        if (taskId == null || taskId.isBlank()) {
            return false;
        }
        if (leased.containsKey(taskId)) {
            return true;
        }
        TaskPersistService db = persist();
        if (db != null) {
            return db.isOpen(taskId);
        }
        synchronized (this) {
            for (Map<String, Object> task : queue) {
                if (taskId.equals(String.valueOf(task.get("task_id")))) {
                    return true;
                }
            }
        }
        return false;
    }

    /**
     * 等待任务进入终态（完成或失败）。
     *
     * @param taskId  任务 ID
     * @param timeout 最长等待
     * @return 终态任务；超时为空
     */
    public Optional<Map<String, Object>> awaitFinished(String taskId, Duration timeout) {
        long deadline = System.nanoTime() + Math.max(timeout.toNanos(), 0);
        TaskPersistService db = persist();
        if (db != null) {
            while (true) {
                Optional<Map<String, Object>> done = db.loadFinished(taskId);
                if (done.isPresent()) {
                    finished.put(taskId, new LinkedHashMap<>(done.get()));
                    return done;
                }
                long remainingMs = TimeUnit.NANOSECONDS.toMillis(deadline - System.nanoTime());
                if (remainingMs <= 0) {
                    return Optional.empty();
                }
                try {
                    Thread.sleep(Math.min(200L, remainingMs));
                } catch (InterruptedException ex) {
                    Thread.currentThread().interrupt();
                    return Optional.empty();
                }
            }
        }
        synchronized (finishedLock) {
            while (!finished.containsKey(taskId)) {
                long remainingMs = TimeUnit.NANOSECONDS.toMillis(deadline - System.nanoTime());
                if (remainingMs <= 0) {
                    return Optional.empty();
                }
                try {
                    finishedLock.wait(Math.min(200L, remainingMs));
                } catch (InterruptedException ex) {
                    Thread.currentThread().interrupt();
                    return Optional.empty();
                }
            }
            return Optional.of(new LinkedHashMap<>(finished.get(taskId)));
        }
    }

    private void signalFinished() {
        synchronized (finishedLock) {
            finishedLock.notifyAll();
        }
    }

    private Map<String, Object> assertLease(String taskId, String leaseToken) {
        Map<String, Object> task = leased.get(taskId);
        if (task != null) {
            if (leaseToken == null || !leaseToken.equals(String.valueOf(task.get("lease_token")))) {
                throw InternalApiException.conflict("lease_token 不匹配");
            }
            return task;
        }
        TaskPersistService db = persist();
        if (db != null) {
            Optional<Map<String, Object>> loaded = db.loadLeased(taskId, leaseToken);
            if (loaded.isPresent()) {
                leased.put(taskId, new LinkedHashMap<>(loaded.get()));
                return loaded.get();
            }
            throw InternalApiException.notFound("task not leased: " + taskId);
        }
        throw InternalApiException.notFound("task not leased: " + taskId);
    }

    private static Map<String, Object> defaultControl() {
        Map<String, Object> ctrl = new LinkedHashMap<>();
        ctrl.put("cancel_requested", false);
        ctrl.put("cancel_reason", "");
        ctrl.put("pause_requested", false);
        ctrl.put("pause_reason", "");
        ctrl.put("queue_depth", 0);
        return ctrl;
    }

    private TaskPersistService persist() {
        return persistProvider.getIfAvailable();
    }

    private void persistRequired(java.util.function.Consumer<TaskPersistService> action) {
        TaskPersistService persist = persist();
        if (persist == null) {
            return;
        }
        action.accept(persist);
    }

    private static String stringOr(Object value, String fallback) {
        if (value == null) {
            return fallback;
        }
        String text = String.valueOf(value);
        return text.isBlank() ? fallback : text;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> castMap(Map<?, ?> map) {
        return (Map<String, Object>) map;
    }
}
