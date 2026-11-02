package cn.aiworkbench.service.integration.agent;

import cn.aiworkbench.service.internalapi.task.InMemoryTaskRuntime;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Java 侧对话桥：调 Python 意图，若 {@code need_task} 则入队供 Worker claim。
 */
@Service
@RequiredArgsConstructor
public class ChatBridgeService {

    private final AgentApiClient agentApiClient;
    private final InMemoryTaskRuntime taskRuntime;

    /**
     * 转发对话；需要长任务时自动入队。
     *
     * @param request 对话请求
     * @return Python 响应；若已入队，在返回对象上不改契约字段，任务已进队列
     */
    public AgentChatResponse handle(AgentChatRequest request) {
        AgentChatResponse response = agentApiClient.chat(request);
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
}
