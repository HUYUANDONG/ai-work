package cn.aiworkbench.service.conversation.infra;

import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * {@code ai_message} 表行。
 */
@Getter
@Setter
public class AiMessageDO {

    private Long id;
    private String conversationId;
    private String userId;
    private String role;
    private String content;
    private String intent;
    private String taskId;
    private Boolean streamInterrupted;
    private LocalDateTime createdAt;
}
