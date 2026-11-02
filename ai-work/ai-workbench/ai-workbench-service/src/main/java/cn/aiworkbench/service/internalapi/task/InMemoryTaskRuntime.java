package cn.aiworkbench.service.internalapi.task;

import cn.aiworkbench.service.internalapi.support.InternalApiException;
import org.springframework.stereotype.Component;

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

/**
 * 内存任务运行时：领取、进度、心跳、完成/失败。正式版可换 DB/Redis。
 */
@Component
public class InMemoryTaskRuntime {

    private final Deque<Map<String, Object>> queue = new ArrayDeque<>();
    private final Map<String, Map<String, Object>> leased = new ConcurrentHashMap<>();
    private final Map<String, Map<String, Object>> control = new ConcurrentHashMap<>();
    private final Map<String, List<Map<String, Object>>> progress = new ConcurrentHashMap<>();
    private final Map<String, List<Map<String, Object>>> messageQueue = new ConcurrentHashMap<>();

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
        task.put("input", input instanceof Map<?, ?> m ? new LinkedHashMap<>(castMap(m)) : new LinkedHashMap<>());
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
        assertLease(taskId, leaseToken);
        progress.computeIfAbsent(taskId, id -> new ArrayList<>()).add(event == null ? Map.of() : new LinkedHashMap<>(event));
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
        Map<String, Object> ctrl = new LinkedHashMap<>(control.computeIfAbsent(taskId, id -> defaultControl()));
        ctrl.put("progress", progressText == null ? "" : progressText);
        String conversationId = String.valueOf(task.get("conversation_id"));
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
        assertLease(taskId, leaseToken);
        Map<String, Object> task = leased.remove(taskId);
        if (task != null) {
            task.put("status", "COMPLETED");
            task.put("complete_body", body);
        }
    }

    /**
     * 失败任务。
     *
     * @param taskId     任务 ID
     * @param leaseToken 租约
     * @param body       失败载荷
     */
    public void fail(String taskId, String leaseToken, Map<String, Object> body) {
        assertLease(taskId, leaseToken);
        Map<String, Object> task = leased.remove(taskId);
        if (task != null) {
            task.put("status", "FAILED");
            task.put("fail_body", body);
        }
    }

    /**
     * 标记取消（前端/Java 侧写入）。
     *
     * @param taskId 任务 ID
     * @param reason 原因
     */
    public void requestCancel(String taskId, String reason) {
        Map<String, Object> ctrl = control.computeIfAbsent(taskId, id -> defaultControl());
        ctrl.put("cancel_requested", true);
        ctrl.put("cancel_reason", reason == null ? "" : reason);
    }

    /**
     * 标记暂停。
     *
     * @param taskId 任务 ID
     * @param reason 原因
     */
    public void requestPause(String taskId, String reason) {
        Map<String, Object> ctrl = control.computeIfAbsent(taskId, id -> defaultControl());
        ctrl.put("pause_requested", true);
        ctrl.put("pause_reason", reason == null ? "" : reason);
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
        return task == null ? Optional.empty() : Optional.of(new LinkedHashMap<>(task));
    }

    private Map<String, Object> assertLease(String taskId, String leaseToken) {
        Map<String, Object> task = leased.get(taskId);
        if (task == null) {
            throw InternalApiException.notFound("task not leased: " + taskId);
        }
        if (leaseToken == null || !leaseToken.equals(String.valueOf(task.get("lease_token")))) {
            throw InternalApiException.conflict("lease_token 不匹配");
        }
        return task;
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
