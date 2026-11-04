package cn.aiworkbench.service.internalapi.report;

import cn.aiworkbench.service.internalapi.support.InternalApiException;
import cn.aiworkbench.service.internalapi.task.InMemoryTaskRuntime;
import cn.aiworkbench.service.persist.ReportPersistService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 爆品 / 质检报告的进程内缓存；MySQL 打开时再双写 {@code ai_explosion_*} 表。
 *
 * <p>本类注解：
 * <ul>
 *   <li>{@code @Slf4j} — Lombok，不是 Spring。编译期生成 {@code private static final Logger log}，
 *       所以下面能直接写 {@code log.warn(...)}。</li>
 *   <li>{@code @Component} — Spring 核心。把这个类注册成 Bean，别的类才能被注入到它、它也能注入别人。
 *       {@code @Service} / {@code @Repository} / {@code @Controller} 都是它的语义化特化，扫描方式一样。</li>
 * </ul>
 *
 * <p>{@link ObjectProvider} 是 Spring 提供的「可选依赖」：{@link ReportPersistService} 带
 * {@code @ConditionalOnProperty}，关库时根本没有这个 Bean。用 {@code getIfAvailable()} 拿不到就返回 {@code null}，
 * 不会像直接注入那样启动失败。
 */
@Slf4j
@Component
public class InMemoryReportStore {

    private final InMemoryTaskRuntime taskRuntime;
    private final ObjectProvider<ReportPersistService> persistProvider;

    /**
     * 唯一构造器 → Spring 自动按类型注入参数（不必写 {@code @Autowired}）。
     *
     * @param taskRuntime     用 taskId 反查会话 / 用户
     * @param persistProvider 可选落库；关 MySQL 时 {@code getIfAvailable()} 为 null
     */
    public InMemoryReportStore(
            InMemoryTaskRuntime taskRuntime,
            ObjectProvider<ReportPersistService> persistProvider) {
        this.taskRuntime = taskRuntime;
        this.persistProvider = persistProvider;
    }

    /** taskId → 整份报告。{@link ConcurrentHashMap}：多线程（HTTP 线程）同时写不会坏。 */
    private final Map<String, Map<String, Object>> byTaskId = new ConcurrentHashMap<>();
    /** conversationId → 该会话报告列表（新的在前）。 */
    private final Map<String, List<Map<String, Object>>> byConversation = new ConcurrentHashMap<>();
    /** conversationId → 归属 userId，防止串会话。 */
    private final Map<String, String> conversationOwner = new ConcurrentHashMap<>();

    /**
     * 覆盖写入爆品或质检报告：先写内存，再尝试落库。
     *
     * @param taskId   任务 ID
     * @param taskType {@code EXPLOSION} / {@code QUALITY}
     * @param report   {@code header} + {@code items}
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
        ReportPersistService persist = persistProvider.getIfAvailable();
        if (persist != null) {
            try {
                persist.upsert(taskId, taskType, conversationId, userId, header, (List<?>) entry.get("items"));
            } catch (Exception ex) {
                log.warn("report persist failed taskId={}", taskId, ex);
            }
        }
    }

    /**
     * 读取会话最近报告：内存没有再回源 MySQL（Java 刚重启时走这条）。
     *
     * @param conversationId 会话
     * @param userId         归属用户
     * @param limit          条数
     * @return 契约响应 {@code conversation_id} + {@code reports}
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
        List<Map<String, Object>> slice = all.stream()
                .limit(safeLimit)
                .<Map<String, Object>>map(LinkedHashMap::new)
                .toList();
        if (slice.isEmpty()) {
            ReportPersistService persist = persistProvider.getIfAvailable();
            if (persist != null) {
                try {
                    slice = persist.listByConversation(conversationId, userId, safeLimit);
                } catch (Exception ex) {
                    log.warn("report list from db failed conversationId={}", conversationId, ex);
                }
            }
        }
        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("conversation_id", conversationId);
        resp.put("reports", slice);
        return resp;
    }

    /**
     * 优先用报告头里的会话 ID，没有再问任务运行时。
     *
     * @param taskId 任务
     * @param header 报告头
     * @return 会话 ID
     */
    private String resolveConversationId(String taskId, Map<String, Object> header) {
        Object fromHeader = header.get("conversation_id");
        if (fromHeader != null && !String.valueOf(fromHeader).isBlank()) {
            return String.valueOf(fromHeader);
        }
        return taskRuntime.findLeased(taskId)
                .map(t -> String.valueOf(t.get("conversation_id")))
                .orElse("c-unknown");
    }

    /**
     * 优先用报告头里的用户 ID，没有再问任务运行时。
     *
     * @param taskId 任务
     * @param header 报告头
     * @return 用户 ID
     */
    private String resolveUserId(String taskId, Map<String, Object> header) {
        Object fromHeader = header.get("user_id");
        if (fromHeader != null && !String.valueOf(fromHeader).isBlank()) {
            return String.valueOf(fromHeader);
        }
        return taskRuntime.findLeased(taskId)
                .map(t -> String.valueOf(t.get("user_id")))
                .orElse("u-unknown");
    }

    /**
     * 把不确定类型的 header 收成可写 Map。
     *
     * <p>{@code @SuppressWarnings("unchecked")} 是 JDK 自带，不是 Spring：
     * 告诉编译器「这里的 {@code Map<?, ?>} 我知道就是 {@code Map<String, Object>}，别告警」。
     *
     * @param value JSON 里的 header
     * @return 可修改副本；不是 Map 则空 Map
     */
    @SuppressWarnings("unchecked")
    private static Map<String, Object> asMap(Object value) {
        if (value instanceof Map<?, ?> map) {
            return new LinkedHashMap<>((Map<String, Object>) map);
        }
        return new LinkedHashMap<>();
    }
}
