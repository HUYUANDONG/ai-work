package cn.aiworkbench.service.persist.infra;

import lombok.Getter;
import lombok.Setter;

/**
 * {@code ai_task} 行。
 */
@Getter
@Setter
public class AiTaskDO {

    private String taskId;
    private String taskType;
    private String taskStatus;
    private String userId;
    private String merchantId;
    private String conversationId;
    private String threadId;
    private String currentRunId;
    private String leaseToken;
    private String leaseOwner;
    private String inputJson;
    private String nextAction;
    private String workflowVersion;
    private String resultJson;
    private String errorCode;
    private String errorMessage;
    private String idempotencyKey;
    private String pauseReason;
    private String cancelReason;
    private java.time.LocalDateTime pauseRequestedAt;
    private java.time.LocalDateTime cancelRequestedAt;
}
