package cn.aiworkbench.service.integration.agent;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;

/**
 * Java → Python {@code POST /internal/chat} 请求。
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class AgentChatRequest {

    private String conversationId;
    private String userId;
    private String message;
    private List<Map<String, Object>> history;
    /**
     * 上一轮任务意图，供短句「近7天」继承筛爆品/质检。
     */
    private String lastIntent;
    /**
     * 上一轮任务入参。
     */
    private Map<String, Object> lastTaskInput;
    private String activeTaskId;
    private boolean queueMessage;
}
