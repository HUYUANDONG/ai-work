package cn.aiworkbench.service.integration.agent;

import cn.aiworkbench.common.security.identity.IdentityContext;
import cn.aiworkbench.service.conversation.application.ConversationMemoryService;
import cn.aiworkbench.service.conversation.application.ConversationSessionState;
import cn.aiworkbench.service.conversation.sse.ConversationSseHub;
import cn.aiworkbench.service.internalapi.task.InMemoryTaskRuntime;
import cn.hutool.core.util.StrUtil;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Java 侧对话桥：调 Python；长任务入队等待；会话 STM/LTM 以 DB 为准（MySQL 开启时）。
 */
@Slf4j
@Service
public class ChatBridgeService {

    /** 从库 hydrate 的近期原文条数（摘要改由 Python LLM 高水位触发，Java 不再截断拼行）。 */
    private static final int HYDRATE_LIMIT = 40;

    private final AgentApiClient agentApiClient;
    private final InMemoryTaskRuntime taskRuntime;
    private final ConversationSseHub sseHub;
    private final ObjectProvider<ConversationMemoryService> memoryProvider;
    /** 进程内 L1 热缓存；DB 为 source of truth。 */
    private final Map<String, ConversationContext> contexts = new ConcurrentHashMap<>();

    @Value("${wb.agent.wait-task-seconds:90}")
    private long waitTaskSeconds;

    /**
     * @param agentApiClient  Python 客户端
     * @param taskRuntime     任务运行时
     * @param sseHub          会话 SSE
     * @param memoryProvider  可选 DB 记忆（mysql 关闭时为空）
     */
    public ChatBridgeService(
            AgentApiClient agentApiClient,
            InMemoryTaskRuntime taskRuntime,
            ConversationSseHub sseHub,
            ObjectProvider<ConversationMemoryService> memoryProvider) {
        this.agentApiClient = agentApiClient;
        this.taskRuntime = taskRuntime;
        this.sseHub = sseHub;
        this.memoryProvider = memoryProvider;
    }

    /**
     * 转发对话；需要长任务时自动入队，并尽量把分析结果拼进本轮回复。
     *
     * @param request 对话请求
     * @return Python 结构化响应（可能已附上 Worker 结果）
     */
    public AgentChatResponse handle(AgentChatRequest request) {
        fillIdentity(request);
        ConversationContext ctx = contextOf(request.getConversationId());
        hydrateFromMemory(request, ctx);
        String conversationId = StrUtil.blankToDefault(request.getConversationId(), "c-unknown");
        sseHub.publish(conversationId, "thinking", Map.of(
                "stage", "chat_started",
                "title", "正在理解你的问题…",
                "detail", ""
        ));
        AgentChatResponse response = agentApiClient.chat(request);
        if (response.getNeedTask() != null && !response.isClarifyPending()) {
            Map<String, Object> created = enqueue(request, response);
            String taskId = String.valueOf(created.get("task_id"));
            ctx.activeTaskId = taskId;
            mergeUiHint(response, "active_task_id", taskId);
            sseHub.publish(conversationId, "thinking", Map.of(
                    "stage", "task_enqueued",
                    "title", "已开始分析，思考过程会实时推送…",
                    "detail", "task_id=" + taskId,
                    "task_id", taskId
            ));
            attachTaskOutcome(response, taskId);
            Object status = response.getUiHints() == null ? null : response.getUiHints().get("task_status");
            if ("PAUSED".equals(status)) {
                // 保留 taskId，便于「继续」对同一任务 resume
                ctx.activeTaskId = taskId;
                mergeUiHint(response, "allow_resume", true);
                mergeUiHint(response, "task_status", "PAUSED");
            } else if ("COMPLETED".equals(status)
                    || "FAILED".equals(status)
                    || "CANCELLED".equals(status)) {
                ctx.activeTaskId = null;
            }
        }
        rememberTurn(request, response, ctx);
        String reply = safeReply(response);
        if (StrUtil.isNotBlank(reply)) {
            sseHub.publish(conversationId, "reply", Map.of(
                    "reply", reply,
                    "intent", StrUtil.blankToDefault(response.getIntent(), "")
            ));
        }
        sseHub.publish(conversationId, "done", Map.of("ok", true));
        return response;
    }

    /**
     * @param conversationId 会话 ID
     * @return 热缓存上下文
     */
    private ConversationContext contextOf(String conversationId) {
        String key = StrUtil.blankToDefault(conversationId, "c-unknown");
        return contexts.computeIfAbsent(key, id -> new ConversationContext());
    }

    /**
     * @param request 对话请求
     */
    private void fillIdentity(AgentChatRequest request) {
        if (StrUtil.isBlank(request.getUserId())) {
            request.setUserId(IdentityContext.userId());
        }
    }

    /**
     * 从 DB（优先）或进程缓存补 history / LTM 槽位。
     *
     * @param request 对话请求
     * @param ctx     热缓存
     */
    private void hydrateFromMemory(AgentChatRequest request, ConversationContext ctx) {
        ConversationMemoryService memory = memoryProvider.getIfAvailable();
        String conversationId = request.getConversationId();
        String userId = request.getUserId();

        if (memory != null && StrUtil.isNotBlank(conversationId) && StrUtil.isNotBlank(userId)) {
            try {
                String titleHint = StrUtil.maxLength(StrUtil.blankToDefault(request.getMessage(), "新对话"), 40);
                memory.ensureConversation(conversationId, userId, titleHint);
                ConversationSessionState state = memory.loadState(conversationId);
                applyStateToContext(state, ctx, true);
                // 有摘要水位：只拉水位之后的原文；否则拉近期窗口
                List<Map<String, Object>> dbHistory;
                if (ctx.summaryThroughMessageId != null && ctx.summaryThroughMessageId > 0
                        && StrUtil.isNotBlank(ctx.workingSummary)) {
                    dbHistory = memory.historyAfterSummary(
                            conversationId, ctx.summaryThroughMessageId, HYDRATE_LIMIT);
                } else {
                    dbHistory = memory.recentHistory(conversationId, HYDRATE_LIMIT);
                }
                if (!dbHistory.isEmpty() || StrUtil.isNotBlank(ctx.workingSummary)) {
                    ctx.history.clear();
                    ctx.history.addAll(dbHistory);
                }
            } catch (Exception ex) {
                log.warn("hydrate conversation memory from DB failed id={}", conversationId, ex);
            }
        }

        // 请求未带 history 时用服务端（DB/缓存）短窗；带了则仍以服务端为准覆盖（source of truth）
        if (ctx.history != null && !ctx.history.isEmpty()) {
            request.setHistory(new ArrayList<>(ctx.history));
        } else if (request.getHistory() == null) {
            request.setHistory(new ArrayList<>());
        }

        if (StrUtil.isBlank(request.getLastIntent()) && StrUtil.isNotBlank(ctx.lastIntent)) {
            request.setLastIntent(ctx.lastIntent);
        }
        Map<String, Object> task = request.getLastTaskInput() == null || request.getLastTaskInput().isEmpty()
                ? (ctx.lastTaskInput == null ? new LinkedHashMap<>() : new LinkedHashMap<>(ctx.lastTaskInput))
                : new LinkedHashMap<>(request.getLastTaskInput());
        if (ctx.adviceOfferPending) {
            task.putIfAbsent("advice_offer_pending", true);
        }
        putIfMissing(task, "goal_mode", ctx.goalMode);
        putIfMissing(task, "time_window_days", ctx.timeWindowDays);
        putIfMissing(task, "focus_slots", ctx.focusSlots);
        putIfMissing(task, "merchant_id", ctx.merchantId);
        putIfMissing(task, "last_report_task_id", ctx.lastReportTaskId);
        if (!task.isEmpty()) {
            request.setLastTaskInput(task);
        }
        if (StrUtil.isNotBlank(ctx.workingSummary)) {
            request.setWorkingSummary(ctx.workingSummary);
        }
        if (ctx.episodes != null && !ctx.episodes.isEmpty()) {
            request.setEpisodes(new ArrayList<>(ctx.episodes));
        }

        dropStaleActiveTask(ctx);
        if (isRetryMessage(request.getMessage())) {
            request.setActiveTaskId(null);
            ctx.activeTaskId = null;
        } else if (StrUtil.isBlank(request.getActiveTaskId()) && StrUtil.isNotBlank(ctx.activeTaskId)) {
            request.setActiveTaskId(ctx.activeTaskId);
        }
    }

    /**
     * @param state     DB 状态
     * @param ctx       热缓存
     * @param overwrite true 时以 DB 为准（含清空）
     */
    private static void applyStateToContext(
            ConversationSessionState state, ConversationContext ctx, boolean overwrite) {
        if (state == null) {
            return;
        }
        if (overwrite || StrUtil.isNotBlank(state.getLastIntent())) {
            ctx.lastIntent = state.getLastIntent();
        }
        if (overwrite || (state.getLastTaskInput() != null && !state.getLastTaskInput().isEmpty())) {
            ctx.lastTaskInput = state.getLastTaskInput() == null
                    ? new LinkedHashMap<>()
                    : new LinkedHashMap<>(state.getLastTaskInput());
        }
        if (overwrite || StrUtil.isNotBlank(state.getActiveTaskId())) {
            ctx.activeTaskId = state.getActiveTaskId();
        }
        ctx.adviceOfferPending = state.isAdviceOfferPending();
        if (overwrite || StrUtil.isNotBlank(state.getGoalMode())) {
            ctx.goalMode = state.getGoalMode();
        }
        if (overwrite || state.getTimeWindowDays() != null) {
            ctx.timeWindowDays = state.getTimeWindowDays();
        }
        if (overwrite || state.getFocusSlots() != null) {
            ctx.focusSlots = state.getFocusSlots();
        }
        if (overwrite || StrUtil.isNotBlank(state.getMerchantId())) {
            ctx.merchantId = state.getMerchantId();
        }
        if (overwrite || StrUtil.isNotBlank(state.getLastReportTaskId())) {
            ctx.lastReportTaskId = state.getLastReportTaskId();
        }
        if (overwrite || StrUtil.isNotBlank(state.getWorkingSummary())) {
            ctx.workingSummary = state.getWorkingSummary();
        }
        if (overwrite || state.getSummaryThroughMessageId() != null) {
            ctx.summaryThroughMessageId = state.getSummaryThroughMessageId();
        }
        if (overwrite || (state.getEpisodes() != null && !state.getEpisodes().isEmpty())) {
            ctx.episodes.clear();
            if (state.getEpisodes() != null) {
                ctx.episodes.addAll(state.getEpisodes());
            }
        }
    }

    /**
     * @param request  对话请求
     * @param response Python 响应
     * @return 入队后的任务
     */
    private Map<String, Object> enqueue(AgentChatRequest request, AgentChatResponse response) {
        Map<String, Object> task = new LinkedHashMap<>();
        task.put("task_type", response.getNeedTask().getTaskType());
        task.put("conversation_id", request.getConversationId());
        task.put("user_id", request.getUserId());
        task.put("input", response.getNeedTask().getInput() == null
                ? Map.of()
                : response.getNeedTask().getInput());
        return taskRuntime.enqueue(task);
    }

    /**
     * @param response 对话响应
     * @param taskId   任务 ID
     */
    private void attachTaskOutcome(AgentChatResponse response, String taskId) {
        if (waitTaskSeconds <= 0) {
            return;
        }
        Optional<Map<String, Object>> done = taskRuntime.awaitFinished(
                taskId, Duration.ofSeconds(waitTaskSeconds));
        if (done.isEmpty()) {
            log.warn("task {} not finished within {}s; worker may be down", taskId, waitTaskSeconds);
            response.setReply(safeReply(response)
                    + "\n\n分析仍在进行。请确认 Python Agent 已启动（对话服务会顺带拉起 Worker）。"
                    + "完成后可继续在本会话追问报告。");
            mergeUiHint(response, "task_status", "RUNNING");
            return;
        }
        appendFinishedReply(response, done.get());
    }

    /**
     * @param response 对话响应
     * @param done     终态任务
     */
    @SuppressWarnings("unchecked")
    private void appendFinishedReply(AgentChatResponse response, Map<String, Object> done) {
        String status = String.valueOf(done.getOrDefault("status", ""));
        Map<String, Object> body = asMap(done.get("complete_body"));
        if (body.isEmpty()) {
            body = asMap(done.get("fail_body"));
        }
        String summary = firstNonBlank(body.get("summary"), body.get("message"), body.get("error_code"));
        StringBuilder reply = new StringBuilder(safeReply(response)).append("\n\n");
        String errorCode = firstNonBlank(body.get("error_code"), done.get("status"));
        if ("COMPLETED".equals(status)) {
            reply.append("分析完成：\n").append(StrUtil.blankToDefault(summary, "报告已生成。"));
            Object meta = body.get("result_meta");
            if (meta instanceof Map<?, ?> metaMap) {
                Object download = metaMap.get("download");
                if (download instanceof Map<?, ?> downloadMap) {
                    mergeUiHint(response, "download", new LinkedHashMap<>((Map<String, Object>) downloadMap));
                    Object url = downloadMap.get("url");
                    if (url != null && !String.valueOf(url).isBlank()) {
                        reply.append("\n下载：").append(url);
                    }
                }
            }
        } else if ("PAUSED".equals(status) || "PAUSED".equals(errorCode)) {
            reply.append("分析已暂停。").append(StrUtil.isBlank(summary) ? "" : (" " + summary));
            reply.append("\n可点「继续」从断点接着跑，或再说「再试一次」重新开跑。");
            status = "PAUSED";
        } else if ("CANCELLED".equals(status) || "CANCELLED".equals(errorCode)) {
            reply.append("分析已取消。").append(StrUtil.isBlank(summary) ? "" : (" " + summary));
            status = "CANCELLED";
        } else {
            reply.append("分析失败：").append(StrUtil.blankToDefault(summary, status));
        }
        response.setReply(reply.toString());
        mergeUiHint(response, "task_status", status);
    }

    /**
     * 写 STM 消息 + LTM 槽位（内存 + 可选 DB）。
     *
     * @param request  本轮请求
     * @param response Python 响应
     * @param ctx      热缓存
     */
    private void rememberTurn(
            AgentChatRequest request,
            AgentChatResponse response,
            ConversationContext ctx) {
        String conversationId = request.getConversationId();
        if (conversationId == null || conversationId.isBlank()) {
            return;
        }
        String userId = StrUtil.blankToDefault(request.getUserId(), IdentityContext.userId());
        String taskId = null;
        if (response.getUiHints() != null && response.getUiHints().get("active_task_id") != null) {
            taskId = String.valueOf(response.getUiHints().get("active_task_id"));
        } else if (StrUtil.isNotBlank(ctx.activeTaskId)) {
            taskId = ctx.activeTaskId;
        }

        ctx.history.add(turn("user", request.getMessage(), null));
        ctx.history.add(turn("assistant", response.getReply(), response.getIntent()));
        if (StrUtil.isNotBlank(response.getWorkingSummary())) {
            ctx.workingSummary = response.getWorkingSummary();
        }
        if (response.getSummaryThroughMessageId() != null && response.getSummaryThroughMessageId() > 0) {
            ctx.summaryThroughMessageId = response.getSummaryThroughMessageId();
        }

        if (StrUtil.isNotBlank(response.getIntent())) {
            String intent = response.getIntent();
            if ("EXPLOSION".equals(intent) || "QUALITY".equals(intent)) {
                ctx.lastIntent = intent;
            }
        }
        if (response.getNeedTask() != null && response.getNeedTask().getInput() != null) {
            ctx.lastTaskInput = new LinkedHashMap<>(response.getNeedTask().getInput());
            Object include = ctx.lastTaskInput.get("include_advise");
            if ("EXPLOSION".equals(response.getIntent())) {
                ctx.adviceOfferPending = !Boolean.TRUE.equals(include) && !"true".equals(String.valueOf(include));
                ctx.lastTaskInput.put("advice_offer_pending", ctx.adviceOfferPending);
            }
            applySlotsFromTaskInput(ctx, ctx.lastTaskInput);
        }
        // 任务完成后：若未含建议，保持待确认；写 episode
        Object taskStatus = response.getUiHints() == null ? null : response.getUiHints().get("task_status");
        if ("COMPLETED".equals(taskStatus)) {
            if (StrUtil.isNotBlank(taskId)) {
                ctx.lastReportTaskId = taskId;
                ctx.addEpisode(buildEpisode(ctx, taskId, response));
            }
            if (ctx.lastTaskInput != null) {
                Object include = ctx.lastTaskInput.get("include_advise");
                boolean included = Boolean.TRUE.equals(include) || "true".equals(String.valueOf(include));
                if (!included && "EXPLOSION".equals(ctx.lastIntent)) {
                    ctx.adviceOfferPending = true;
                    ctx.lastTaskInput.put("advice_offer_pending", true);
                }
            }
        }
        if ("ADVISE".equals(response.getIntent()) || "ADVISE_DECLINED".equals(response.getIntent())) {
            ctx.adviceOfferPending = false;
            if (ctx.lastTaskInput != null) {
                ctx.lastTaskInput.put("advice_offer_pending", false);
            }
        }

        ConversationMemoryService memory = memoryProvider.getIfAvailable();
        if (memory == null || StrUtil.isBlank(userId)) {
            return;
        }
        try {
            String titleHint = StrUtil.maxLength(StrUtil.blankToDefault(request.getMessage(), "新对话"), 40);
            memory.ensureConversation(conversationId, userId, titleHint);
            memory.appendMessage(conversationId, userId, "user", request.getMessage(), null, null);
            memory.appendMessage(
                    conversationId,
                    userId,
                    "assistant",
                    response.getReply(),
                    response.getIntent(),
                    taskId);
            memory.updateTitleIfDefault(conversationId, titleHint);
            ConversationSessionState state = snapshotState(ctx);
            memory.saveState(conversationId, state);
        } catch (Exception ex) {
            log.warn("persist conversation memory failed id={}", conversationId, ex);
        }
    }

    /**
     * @param response 响应
     * @param key      键
     * @param value    值
     */
    private static void mergeUiHint(AgentChatResponse response, String key, Object value) {
        Map<String, Object> hints = response.getUiHints();
        if (hints == null) {
            hints = new LinkedHashMap<>();
            response.setUiHints(hints);
        }
        hints.put(key, value);
    }

    /**
     * @param role    user / assistant
     * @param content 文本
     * @param intent  助手意图
     * @return map
     */
    private static Map<String, Object> turn(String role, String content, String intent) {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("role", role);
        item.put("content", content == null ? "" : content);
        if (intent != null && !intent.isBlank()) {
            item.put("intent", intent);
        }
        return item;
    }

    private static String safeReply(AgentChatResponse response) {
        return response.getReply() == null ? "" : response.getReply();
    }

    private static String firstNonBlank(Object... values) {
        if (values == null) {
            return "";
        }
        for (Object value : values) {
            if (value != null) {
                String text = String.valueOf(value).trim();
                if (!text.isEmpty() && !"null".equals(text)) {
                    return text;
                }
            }
        }
        return "";
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> asMap(Object value) {
        if (value instanceof Map<?, ?> map) {
            return new LinkedHashMap<>((Map<String, Object>) map);
        }
        return new LinkedHashMap<>();
    }

    private void dropStaleActiveTask(ConversationContext ctx) {
        if (StrUtil.isBlank(ctx.activeTaskId)) {
            return;
        }
        var finished = taskRuntime.findFinished(ctx.activeTaskId);
        if (finished.isPresent()) {
            Object status = finished.get().get("status");
            // PAUSED 保留，供继续；其它终态清掉
            if (!"PAUSED".equals(String.valueOf(status))) {
                ctx.activeTaskId = null;
            }
            return;
        }
        if (!taskRuntime.isRunning(ctx.activeTaskId)) {
            ctx.activeTaskId = null;
        }
    }

    private static boolean isRetryMessage(String message) {
        if (StrUtil.isBlank(message)) {
            return false;
        }
        return message.contains("再试")
                || message.contains("再跑")
                || message.contains("重跑")
                || message.contains("再来一")
                || message.contains("重新分析")
                || message.contains("重新跑")
                || message.contains("再筛");
    }

    private static ConversationSessionState snapshotState(ConversationContext ctx) {
        ConversationSessionState state = new ConversationSessionState();
        state.setLastIntent(ctx.lastIntent);
        state.setLastTaskInput(ctx.lastTaskInput == null
                ? new LinkedHashMap<>()
                : new LinkedHashMap<>(ctx.lastTaskInput));
        state.setActiveTaskId(ctx.activeTaskId);
        state.setAdviceOfferPending(ctx.adviceOfferPending);
        state.setGoalMode(ctx.goalMode);
        state.setTimeWindowDays(ctx.timeWindowDays);
        state.setFocusSlots(ctx.focusSlots);
        state.setMerchantId(ctx.merchantId);
        state.setLastReportTaskId(ctx.lastReportTaskId);
        state.setWorkingSummary(ctx.workingSummary);
        state.setSummaryThroughMessageId(ctx.summaryThroughMessageId);
        state.setEpisodes(new ArrayList<>(ctx.episodes));
        return state;
    }

    private static void applySlotsFromTaskInput(ConversationContext ctx, Map<String, Object> input) {
        if (input == null) {
            return;
        }
        Object goal = input.get("goal_mode");
        if (goal != null && !String.valueOf(goal).isBlank()) {
            ctx.goalMode = String.valueOf(goal);
        }
        Object window = input.get("time_window_days");
        if (window instanceof Number n) {
            ctx.timeWindowDays = n.intValue();
        } else if (window != null) {
            try {
                ctx.timeWindowDays = Integer.parseInt(String.valueOf(window));
            } catch (NumberFormatException ignored) {
                // keep previous
            }
        }
        Object slots = input.get("focus_slots");
        if (slots instanceof Number n) {
            ctx.focusSlots = n.intValue();
        } else if (slots != null) {
            try {
                ctx.focusSlots = Integer.parseInt(String.valueOf(slots));
            } catch (NumberFormatException ignored) {
                // keep previous
            }
        }
        Object merchant = input.get("merchant_id");
        if (merchant != null && !String.valueOf(merchant).isBlank()) {
            ctx.merchantId = String.valueOf(merchant);
        }
    }

    private static Map<String, Object> buildEpisode(
            ConversationContext ctx, String taskId, AgentChatResponse response) {
        Map<String, Object> episode = new LinkedHashMap<>();
        episode.put("task_id", taskId);
        episode.put("task_type", StrUtil.blankToDefault(ctx.lastIntent, ""));
        episode.put("summary", episodeSummary(response));
        if (StrUtil.isNotBlank(ctx.goalMode)) {
            episode.put("goal_mode", ctx.goalMode);
        }
        if (ctx.timeWindowDays != null) {
            episode.put("time_window_days", ctx.timeWindowDays);
        }
        if (ctx.focusSlots != null) {
            episode.put("focus_slots", ctx.focusSlots);
        }
        return episode;
    }

    private static String episodeSummary(AgentChatResponse response) {
        String reply = safeReply(response);
        String[] markers = {"分析完成：", "分析已暂停。", "分析已取消。"};
        for (String marker : markers) {
            int idx = reply.lastIndexOf(marker);
            if (idx >= 0) {
                String tail = reply.substring(idx + marker.length()).replace('\n', ' ').trim();
                if (!tail.isBlank()) {
                    return StrUtil.maxLength(tail, 240);
                }
            }
        }
        return StrUtil.maxLength(reply.replace('\n', ' ').trim(), 240);
    }

    private static void putIfMissing(Map<String, Object> map, String key, Object value) {
        if (value == null || map.containsKey(key)) {
            return;
        }
        if (value instanceof String s && s.isBlank()) {
            return;
        }
        map.put(key, value);
    }

    /**
     * 进程内热缓存。
     */
    private static final class ConversationContext {
        private final List<Map<String, Object>> history = new ArrayList<>();
        private String lastIntent;
        private Map<String, Object> lastTaskInput;
        private String activeTaskId;
        private boolean adviceOfferPending;
        private String goalMode;
        private Integer timeWindowDays;
        private Integer focusSlots;
        private String merchantId;
        private String lastReportTaskId;
        private String workingSummary;
        /** 摘要已覆盖到的最大消息 id；其后原文才进模型。 */
        private Long summaryThroughMessageId;
        private final List<Map<String, Object>> episodes = new ArrayList<>();

        private void addEpisode(Map<String, Object> episode) {
            if (episode == null || episode.isEmpty()) {
                return;
            }
            episodes.add(new LinkedHashMap<>(episode));
            if (episodes.size() > 8) {
                episodes.subList(0, episodes.size() - 8).clear();
            }
        }
    }
}
