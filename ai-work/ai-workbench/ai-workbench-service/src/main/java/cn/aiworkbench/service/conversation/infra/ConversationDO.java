package cn.aiworkbench.service.conversation.infra;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class ConversationDO {
    private Long id;
    private String title;
    private String description;
    private String createdAt;
    private String updatedAt;
    private String userId;
}
