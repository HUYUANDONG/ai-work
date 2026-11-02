package cn.aiworkbench.service.integration.agent;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import lombok.Builder;
import lombok.Data;

import java.util.List;
import java.util.Map;

/**
 * Java → Python {@code POST /internal/chat} 请求。
 */
@Data
@Builder
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class AgentChatRequest {

    private String conversationId;
    private String userId;
    private String message;
    private List<Map<String, Object>> history;
    private String activeTaskId;
    private boolean queueMessage;
}
