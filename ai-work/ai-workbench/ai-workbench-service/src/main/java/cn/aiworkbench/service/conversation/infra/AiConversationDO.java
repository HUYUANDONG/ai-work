package cn.aiworkbench.service.conversation.infra;

import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * {@code ai_conversation} 表行。
 */
@Getter
@Setter
public class AiConversationDO {

    private Long id;
    private String conversationId;
    private String userId;
    private String title;
    /** JSON 文本，会话 LTM 槽位。 */
    private String sessionStateJson;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
