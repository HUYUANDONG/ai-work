package cn.aiworkbench.service.internalapi.report;

import cn.aiworkbench.service.internalapi.support.InternalApiException;
import cn.aiworkbench.service.internalapi.task.InMemoryTaskRuntime;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 报告内存仓：按 task_id 覆盖，并挂到 conversation 下供追问读取。
 */
@Component
@RequiredArgsConstructor
public class InMemoryReportStore {

    private final InMemoryTaskRuntime taskRuntime;

    private final Map<String, Map<String, Object>> byTaskId = new ConcurrentHashMap<>();
    private final Map<String, List<Map<String, Object>>> byConversation = new ConcurrentHashMap<>();
    private final Map<String, String> conversationOwner = new ConcurrentHashMap<>();

    /**
     * 覆盖写入爆品或质检报告。
     *
     * @param taskId   任务 ID
     * @param taskType EXPLOSION / QUALITY
     * @param report   header + items
     */
    public void upsert(String taskId, String taskType, Map<String, Object> report) {
        if (report == null) {
            throw InternalApiException.badRequest("report body 不能为空");
        }
        Map<String, Object> header = asMap(report.get("header"));
        header.putIfAbsent("task_id", taskId);

        String conversationId = resolveConversationId(taskId, header);
        String userId = resolveUserId(taskId, header);
        conversationOwner.put(conversationId, userId);

        Map<String, Object> entry = new LinkedHashMap<>();
        entry.put("task_id", taskId);
        entry.put("task_type", taskType);
        entry.put("created_at", Instant.now().toString());
        entry.put("header", header);
        entry.put("items", report.get("items") instanceof List<?> list ? list : List.of());

        byTaskId.put(taskId, entry);
        List<Map<String, Object>> bucket = byConversation.computeIfAbsent(conversationId, id -> new ArrayList<>());
        bucket.removeIf(old -> taskId.equals(String.valueOf(old.get("task_id"))));
        bucket.add(0, entry);
    }

    /**
     * 读取会话最近报告。
     *
     * @param conversationId 会话
     * @param userId         归属用户
     * @param limit          条数
     * @return 契约响应
     */
    public Map<String, Object> listByConversation(String conversationId, String userId, int limit) {
        if (userId == null || userId.isBlank()) {
            throw InternalApiException.badRequest("user_id 必填");
        }
        String owner = conversationOwner.get(conversationId);
        if (owner != null && !owner.equals(userId)) {
            throw InternalApiException.notFound("conversation not found");
        }
        List<Map<String, Object>> all = byConversation.getOrDefault(conversationId, List.of());
        int safeLimit = Math.max(1, limit);
        List<Map<String, Object>> slice = all.stream().limit(safeLimit).map(LinkedHashMap::new).toList();
        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("conversation_id", conversationId);
        resp.put("reports", slice);
        return resp;
    }

    private String resolveConversationId(String taskId, Map<String, Object> header) {
        Object fromHeader = header.get("conversation_id");
        if (fromHeader != null && !String.valueOf(fromHeader).isBlank()) {
            return String.valueOf(fromHeader);
        }
        return taskRuntime.findLeased(taskId)
                .map(t -> String.valueOf(t.get("conversation_id")))
                .orElse("c-unknown");
    }

    private String resolveUserId(String taskId, Map<String, Object> header) {
        Object fromHeader = header.get("user_id");
        if (fromHeader != null && !String.valueOf(fromHeader).isBlank()) {
            return String.valueOf(fromHeader);
        }
        return taskRuntime.findLeased(taskId)
                .map(t -> String.valueOf(t.get("user_id")))
                .orElse("u-unknown");
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> asMap(Object value) {
        if (value instanceof Map<?, ?> map) {
            return new LinkedHashMap<>((Map<String, Object>) map);
        }
        return new LinkedHashMap<>();
    }
}
