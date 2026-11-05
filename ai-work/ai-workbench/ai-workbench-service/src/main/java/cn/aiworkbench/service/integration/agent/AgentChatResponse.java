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
    /** Python 高水位 LLM 深度摘要；有则覆盖本地 workingSummary。 */
    private String workingSummary;
    /** 摘要覆盖到的最大 ai_message.id（含）。 */
    private Long summaryThroughMessageId;
    /** 本轮要写入该运营画像的键值；空则不改画像。 */
    private Map<String, Object> profilePatch;

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
