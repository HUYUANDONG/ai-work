package cn.aiworkbench.service.integration.agent;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import lombok.Data;

import java.util.Map;

/**
 * Python 对话响应。
 */
@Data
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class AgentChatResponse {

    private String intent;
    private String reply;
    private NeedTask needTask;
    private boolean clarifyPending;
    private Map<String, Object> queueAck;
    private Map<String, Object> uiHints;

    /**
     * 需要 Java 创建的长任务。
     */
    @Data
    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public static class NeedTask {
        private String taskType;
        private Map<String, Object> input;
    }
}
