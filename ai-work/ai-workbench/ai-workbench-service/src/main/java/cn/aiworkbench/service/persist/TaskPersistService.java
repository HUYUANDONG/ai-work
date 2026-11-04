package cn.aiworkbench.service.persist;

import cn.aiworkbench.service.persist.infra.AiTaskDO;
import cn.aiworkbench.service.persist.mapper.AiRunMapper;
import cn.aiworkbench.service.persist.mapper.AiTaskMapper;
import cn.hutool.core.util.StrUtil;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/**
 * 任务队列以 {@code ai_task} 为准：入队 / SKIP LOCKED 领取 / 心跳 / 终态。
 */
@Slf4j
@Service
@RequiredArgsConstructor
@ConditionalOnProperty(name = "wb.mysql.enabled", havingValue = "true")
public class TaskPersistService {

    private static final int DEFAULT_LEASE_SECONDS = 120;

    private final AiTaskMapper taskMapper;
    private final AiRunMapper runMapper;
    private final ObjectMapper objectMapper;

    /**
     * 入队落库。
     *
     * @param task 任务
     */
    public void onEnqueue(Map<String, Object> task) {
        if (task == null) {
            return;
        }
        AiTaskDO row = new AiTaskDO();
        row.setTaskId(str(task.get("task_id")));
        row.setTaskType(str(task.get("task_type")));
        row.setTaskStatus("QUEUED");
        row.setUserId(str(task.get("user_id")));
        row.setConversationId(str(task.get("conversation_id")));
        row.setCurrentRunId(str(task.get("run_id")));
        row.setLeaseToken(str(task.get("lease_token")));
        Object input = task.get("input");
        row.setInputJson(json(input));
        if (input instanceof Map<?, ?> map) {
            Object thread = map.get("graph_thread_id");
            row.setThreadId(thread == null ? row.getTaskId() : String.valueOf(thread));
            Object merchant = map.get("merchant_id");
            if (merchant != null) {
                row.setMerchantId(String.valueOf(merchant));
            }
            Object next = map.get("resume_from_checkpoint");
            row.setNextAction(Boolean.TRUE.equals(next) || "true".equals(String.valueOf(next))
                    ? "RESUME" : "START");
        } else {
            row.setThreadId(row.getTaskId());
            row.setNextAction("START");
        }
        row.setIdempotencyKey(row.getTaskId());
        taskMapper.upsertQueued(row);
    }

    /**
     * 从库领取一条（SKIP LOCKED）。租约过期的 RUNNING 会重新领。
     *
     * @param taskTypes 类型
     * @param workflow  版本
     * @param workerId  Worker
     * @return 任务
     */
    @Transactional
    public Optional<Map<String, Object>> claim(List<String> taskTypes, String workflow, String workerId) {
        if (taskTypes == null || taskTypes.isEmpty()) {
            return Optional.empty();
        }
        List<String> types = taskTypes.stream()
                .map(t -> t == null ? "" : t.toUpperCase())
                .filter(t -> !t.isBlank())
                .toList();
        if (types.isEmpty()) {
            return Optional.empty();
        }
        AiTaskDO locked = taskMapper.lockClaimable(types);
        if (locked == null) {
            return Optional.empty();
        }
        String oldRun = locked.getCurrentRunId();
        if ("RUNNING".equals(locked.getTaskStatus()) && StrUtil.isNotBlank(oldRun)) {
            runMapper.markFinished(oldRun, "TIMEOUT", "LEASE_EXPIRED", "租约过期，重新领取");
        }
        String runId = "r-" + UUID.randomUUID().toString().replace("-", "").substring(0, 8);
        String lease = "lease-" + UUID.randomUUID().toString().replace("-", "").substring(0, 8);
        taskMapper.markRunning(locked.getTaskId(), runId, lease, workerId, workflow, DEFAULT_LEASE_SECONDS);
        runMapper.insertRunning(runId, locked.getTaskId(), lease, workerId);
        Map<String, Object> task = toRuntimeTask(locked);
        task.put("run_id", runId);
        task.put("lease_token", lease);
        task.put("lease_seconds", DEFAULT_LEASE_SECONDS);
        task.put("worker_id", workerId);
        task.put("workflow_version", workflow);
        return Optional.of(task);
    }

    /**
     * 心跳并续租，返回暂停/取消标志。
     *
     * @param taskId     任务
     * @param leaseToken 租约
     * @return 控制位
     */
    public Map<String, Object> heartbeat(String taskId, String leaseToken) {
        taskMapper.heartbeat(taskId, leaseToken, DEFAULT_LEASE_SECONDS);
        AiTaskDO row = taskMapper.selectByTaskId(taskId);
        Map<String, Object> ctrl = new LinkedHashMap<>();
        ctrl.put("cancel_requested", row != null && row.getCancelRequestedAt() != null);
        ctrl.put("cancel_reason", row == null ? "" : StrUtil.blankToDefault(row.getCancelReason(), ""));
        ctrl.put("pause_requested", row != null && row.getPauseRequestedAt() != null);
        ctrl.put("pause_reason", row == null ? "" : StrUtil.blankToDefault(row.getPauseReason(), ""));
        return ctrl;
    }

    /**
     * 校验租约并返回运行中任务。
     *
     * @param taskId     任务
     * @param leaseToken 租约
     * @return 任务
     */
    public Optional<Map<String, Object>> loadLeased(String taskId, String leaseToken) {
        AiTaskDO row = taskMapper.selectByTaskId(taskId);
        if (row == null || !"RUNNING".equals(row.getTaskStatus())) {
            return Optional.empty();
        }
        if (leaseToken != null && !leaseToken.equals(row.getLeaseToken())) {
            return Optional.empty();
        }
        return Optional.of(toRuntimeTask(row));
    }

    /**
     * 不校验租约，读进行中任务。
     *
     * @param taskId 任务
     * @return 任务
     */
    public Optional<Map<String, Object>> loadRunning(String taskId) {
        AiTaskDO row = taskMapper.selectByTaskId(taskId);
        if (row == null) {
            return Optional.empty();
        }
        if (!"QUEUED".equals(row.getTaskStatus()) && !"RUNNING".equals(row.getTaskStatus())) {
            return Optional.empty();
        }
        return Optional.of(toRuntimeTask(row));
    }

    /**
     * 读终态（含暂停）。
     *
     * @param taskId 任务
     * @return 终态
     */
    public Optional<Map<String, Object>> loadFinished(String taskId) {
        AiTaskDO row = taskMapper.selectByTaskId(taskId);
        if (row == null) {
            return Optional.empty();
        }
        String mem = toMemStatus(row.getTaskStatus(), row.getErrorCode());
        if (mem == null) {
            return Optional.empty();
        }
        Map<String, Object> done = toRuntimeTask(row);
        done.put("status", mem);
        Map<String, Object> body = parseMap(row.getResultJson());
        if ("COMPLETED".equals(mem)) {
            done.put("complete_body", body);
        } else {
            done.put("fail_body", body);
        }
        return Optional.of(done);
    }

    /**
     * 是否仍在队列或执行中。
     *
     * @param taskId 任务
     * @return true 在跑
     */
    public boolean isOpen(String taskId) {
        AiTaskDO row = taskMapper.selectByTaskId(taskId);
        if (row == null) {
            return false;
        }
        return "QUEUED".equals(row.getTaskStatus()) || "RUNNING".equals(row.getTaskStatus());
    }

    /**
     * 请求取消。
     *
     * @param taskId 任务
     * @param reason 原因
     */
    public void onCancelRequested(String taskId, String reason) {
        if (StrUtil.isBlank(taskId)) {
            return;
        }
        taskMapper.markCancelRequested(taskId, StrUtil.maxLength(reason, 200));
    }

    /**
     * 请求暂停。
     *
     * @param taskId 任务
     * @param reason 原因
     */
    public void onPauseRequested(String taskId, String reason) {
        if (StrUtil.isBlank(taskId)) {
            return;
        }
        taskMapper.markPauseRequested(taskId, StrUtil.maxLength(reason, 200));
    }

    /**
     * 完成。
     *
     * @param task 任务
     * @param body complete 载荷
     */
    public void onComplete(Map<String, Object> task, Map<String, Object> body) {
        finish(task, "SUCCEEDED", "SUCCEEDED", body, null, null);
    }

    /**
     * 失败 / 暂停 / 取消。
     *
     * @param task      任务
     * @param memStatus PAUSED/CANCELLED/FAILED
     * @param body      fail 载荷
     */
    public void onFail(Map<String, Object> task, String memStatus, Map<String, Object> body) {
        String dbStatus = switch (String.valueOf(memStatus)) {
            case "PAUSED" -> "RETRY_WAIT";
            case "CANCELLED" -> "CANCELLED";
            default -> "FAILED";
        };
        String error = body == null ? memStatus : String.valueOf(body.getOrDefault("error_code", memStatus));
        String message = body == null ? "" : String.valueOf(body.getOrDefault("message", body.getOrDefault("summary", "")));
        finish(task, dbStatus, "FAILED", body, error, message);
    }

    private void finish(
            Map<String, Object> task,
            String taskStatus,
            String runStatus,
            Map<String, Object> body,
            String errorCode,
            String errorMessage) {
        if (task == null) {
            return;
        }
        AiTaskDO row = new AiTaskDO();
        row.setTaskId(str(task.get("task_id")));
        row.setTaskStatus(taskStatus);
        row.setResultJson(json(body));
        row.setErrorCode(errorCode);
        row.setErrorMessage(StrUtil.maxLength(errorMessage, 1000));
        taskMapper.markFinished(row);
        String runId = str(task.get("run_id"));
        if (StrUtil.isNotBlank(runId)) {
            runMapper.markFinished(runId, runStatus, errorCode, StrUtil.maxLength(errorMessage, 1000));
        }
    }

    private Map<String, Object> toRuntimeTask(AiTaskDO row) {
        Map<String, Object> task = new LinkedHashMap<>();
        task.put("task_id", row.getTaskId());
        task.put("run_id", row.getCurrentRunId());
        task.put("task_type", row.getTaskType());
        task.put("lease_token", row.getLeaseToken());
        task.put("lease_seconds", DEFAULT_LEASE_SECONDS);
        task.put("conversation_id", row.getConversationId());
        task.put("user_id", row.getUserId());
        task.put("worker_id", row.getLeaseOwner());
        task.put("workflow_version", row.getWorkflowVersion());
        task.put("input", parseMap(row.getInputJson()));
        return task;
    }

    private static String toMemStatus(String dbStatus, String errorCode) {
        if (dbStatus == null) {
            return null;
        }
        return switch (dbStatus) {
            case "SUCCEEDED" -> "COMPLETED";
            case "CANCELLED" -> "CANCELLED";
            case "FAILED" -> "FAILED";
            case "RETRY_WAIT" -> "PAUSED".equals(errorCode) ? "PAUSED" : "FAILED";
            default -> null;
        };
    }

    private Map<String, Object> parseMap(String raw) {
        if (StrUtil.isBlank(raw)) {
            return new LinkedHashMap<>();
        }
        try {
            Map<String, Object> map = objectMapper.readValue(raw, new TypeReference<>() {});
            return map == null ? new LinkedHashMap<>() : new LinkedHashMap<>(map);
        } catch (Exception ex) {
            log.warn("parse task json failed", ex);
            return new LinkedHashMap<>();
        }
    }

    private String json(Object value) {
        if (value == null) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(value);
        } catch (Exception ex) {
            log.warn("serialize task json failed", ex);
            return null;
        }
    }

    private static String str(Object value) {
        return value == null ? null : String.valueOf(value);
    }
}
