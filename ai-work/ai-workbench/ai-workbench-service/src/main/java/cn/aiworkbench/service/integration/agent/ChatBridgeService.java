package cn.aiworkbench.service.integration.agent;

import cn.aiworkbench.service.internalapi.task.InMemoryTaskRuntime;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Java 侧对话桥：调 Python 意图，若 {@code need_task} 则入队供 Worker claim。
 * 前端未带 history 时，用本会话最近轮次补上，避免短句「近 7 天」丢上下文。
 */
@Service
@RequiredArgsConstructor
public class ChatBridgeService {

    private static final int MAX_HISTORY = 8;

    private final AgentApiClient agentApiClient;
    private final InMemoryTaskRuntime taskRuntime;
    private final Map<String, List<Map<String, Object>>> histories = new ConcurrentHashMap<>();

    /**
     * 转发对话；需要长任务时自动入队。
     *
     * @param request 对话请求
     * @return Python 结构化响应
     */
    public AgentChatResponse handle(AgentChatRequest request) {
        if (request.getHistory() == null || request.getHistory().isEmpty()) {
            List<Map<String, Object>> stored = histories.get(request.getConversationId());
            if (stored != null && !stored.isEmpty()) {
                request.setHistory(new ArrayList<>(stored));
            }
        }
        AgentChatResponse response = agentApiClient.chat(request);
        rememberTurn(request, response);
        if (response.getNeedTask() != null && !response.isClarifyPending()) {
            Map<String, Object> task = new LinkedHashMap<>();
            task.put("task_type", response.getNeedTask().getTaskType());
            task.put("conversation_id", request.getConversationId());
            task.put("user_id", request.getUserId());
            task.put("input", response.getNeedTask().getInput() == null
                    ? Map.of()
                    : response.getNeedTask().getInput());
            taskRuntime.enqueue(task);
        }
        return response;
    }

    /**
     * 记下本轮 user/assistant，供下一轮补 history。
     *
     * @param request  本轮请求
     * @param response Python 响应
     */
    private void rememberTurn(AgentChatRequest request, AgentChatResponse response) {
        String conversationId = request.getConversationId();
        if (conversationId == null || conversationId.isBlank()) {
            return;
        }
        List<Map<String, Object>> bucket = histories.computeIfAbsent(conversationId, id -> new ArrayList<>());
        bucket.add(turn("user", request.getMessage(), null));
        bucket.add(turn("assistant", response.getReply(), response.getIntent()));
        if (bucket.size() > MAX_HISTORY) {
            bucket.subList(0, bucket.size() - MAX_HISTORY).clear();
        }
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
}
