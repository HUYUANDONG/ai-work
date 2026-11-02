package cn.aiworkbench.service.conversation.api.dto;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class ConversationResponse {
    private String id;
    private String title;
    private String description;
    private String createdAt;
    private String updatedAt;
}
 
