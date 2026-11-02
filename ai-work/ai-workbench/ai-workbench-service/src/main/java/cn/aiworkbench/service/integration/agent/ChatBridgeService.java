package cn.aiworkbench.service.integration.agent;

import cn.aiworkbench.common.security.identity.IdentityContext;
import cn.aiworkbench.service.internalapi.task.InMemoryTaskRuntime;
import cn.hutool.core.util.StrUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
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
 * Java 侧对话桥：调 Python 意图，若 {@code need_task} 则入队并等待 Worker 回写结果。
 * 前端未带 history / last_intent 时，用本会话最近轮次补上。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ChatBridgeService {

    private static final int MAX_HISTORY = 8;

    private final AgentApiClient agentApiClient;
    private final InMemoryTaskRuntime taskRuntime;
    private final Map<String, ConversationContext> contexts = new ConcurrentHashMap<>();

    @Value("${wb.agent.wait-task-seconds:90}")
    private long waitTaskSeconds;

    /**
     * 转发对话；需要长任务时自动入队，并尽量把分析结果拼进本轮回复。
     *
     * @param request 对话请求
     * @return Python 结构化响应（可能已附上 Worker 结果）
     */
    public AgentChatResponse handle(AgentChatRequest request) {
        fillIdentity(request);
        ConversationContext ctx = contextOf(request.getConversationId());
        hydrateFromContext(request, ctx);
        AgentChatResponse response = agentApiClient.chat(request);
        if (response.getNeedTask() != null && !response.isClarifyPending()) {
            Map<String, Object> created = enqueue(request, response);
            String taskId = String.valueOf(created.get("task_id"));
            ctx.activeTaskId = taskId;
            mergeUiHint(response, "active_task_id", taskId);
            attachTaskOutcome(response, taskId);
            if (response.getUiHints() != null && "COMPLETED".equals(response.getUiHints().get("task_status"))) {
                ctx.activeTaskId = null;
            }
        }
        rememberTurn(request, response, ctx);
        return response;
    }

    /**
     * 当前会话上下文。
     *
     * @param conversationId 会话 ID
     * @return 可变上下文
     */
    private ConversationContext contextOf(String conversationId) {
        String key = StrUtil.blankToDefault(conversationId, "c-unknown");
        return contexts.computeIfAbsent(key, id -> new ConversationContext());
    }

    /**
     * 用登录身份补 userId。
     *
     * @param request 对话请求
     */
    private void fillIdentity(AgentChatRequest request) {
        if (StrUtil.isBlank(request.getUserId())) {
            request.setUserId(IdentityContext.userId());
        }
    }

    /**
     * 前端未带上下文时，用 Java 侧记住的 history / last_intent / 进行中任务补上。
     *
     * @param request 对话请求
     * @param ctx     本会话上下文
     */
    private void hydrateFromContext(AgentChatRequest request, ConversationContext ctx) {
        if (request.getHistory() == null || request.getHistory().isEmpty()) {
            request.setHistory(new ArrayList<>(ctx.history));
        }
        if (StrUtil.isBlank(request.getLastIntent()) && StrUtil.isNotBlank(ctx.lastIntent)) {
            request.setLastIntent(ctx.lastIntent);
        }
        if ((request.getLastTaskInput() == null || request.getLastTaskInput().isEmpty())
                && ctx.lastTaskInput != null && !ctx.lastTaskInput.isEmpty()) {
            request.setLastTaskInput(new LinkedHashMap<>(ctx.lastTaskInput));
        }
        if (StrUtil.isBlank(request.getActiveTaskId()) && StrUtil.isNotBlank(ctx.activeTaskId)) {
            request.setActiveTaskId(ctx.activeTaskId);
        }
    }

    /**
     * 入队一条长任务。
     *
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
     * 等待 Worker 完成并把摘要拼进回复。
     *
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
     * 把完成/失败摘要接到用户可见回复。
     *
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
        } else {
            reply.append("分析失败：").append(StrUtil.blankToDefault(summary, status));
        }
        response.setReply(reply.toString());
        mergeUiHint(response, "task_status", status);
    }

    /**
     * 记下本轮 user/assistant 与任务参数，供下一轮补上下文。
     *
     * @param request  本轮请求
     * @param response Python 响应
     * @param ctx      会话上下文
     */
    private void rememberTurn(
            AgentChatRequest request,
            AgentChatResponse response,
            ConversationContext ctx) {
        String conversationId = request.getConversationId();
        if (conversationId == null || conversationId.isBlank()) {
            return;
        }
        ctx.history.add(turn("user", request.getMessage(), null));
        ctx.history.add(turn("assistant", response.getReply(), response.getIntent()));
        if (ctx.history.size() > MAX_HISTORY) {
            ctx.history.subList(0, ctx.history.size() - MAX_HISTORY).clear();
        }
        if (StrUtil.isNotBlank(response.getIntent())) {
            String intent = response.getIntent();
            if ("EXPLOSION".equals(intent) || "QUALITY".equals(intent)) {
                ctx.lastIntent = intent;
            }
        }
        if (response.getNeedTask() != null && response.getNeedTask().getInput() != null) {
            ctx.lastTaskInput = new LinkedHashMap<>(response.getNeedTask().getInput());
        }
    }

    /**
     * 写入 ui_hints。
     *
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
     * 组装一轮 history 元素。
     *
     * @param role    user / assistant
     * @param content 文本
     * @param intent  助手意图，用户轮为 null
     * @return 有序 map
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

    /**
     * @param response 响应
     * @return 非空回复
     */
    private static String safeReply(AgentChatResponse response) {
        return response.getReply() == null ? "" : response.getReply();
    }

    /**
     * @param values 候选
     * @return 第一个非空字符串
     */
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

    /**
     * @param value 可能是 map
     * @return 可变副本
     */
    @SuppressWarnings("unchecked")
    private static Map<String, Object> asMap(Object value) {
        if (value instanceof Map<?, ?> map) {
            return new LinkedHashMap<>((Map<String, Object>) map);
        }
        return new LinkedHashMap<>();
    }

    /**
     * 单会话在 Java 进程内的上下文。
     */
    private static final class ConversationContext {
        private final List<Map<String, Object>> history = new ArrayList<>();
        private String lastIntent;
        private Map<String, Object> lastTaskInput;
        private String activeTaskId;
    }
}
