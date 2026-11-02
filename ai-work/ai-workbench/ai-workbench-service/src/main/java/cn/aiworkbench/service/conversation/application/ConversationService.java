package cn.aiworkbench.service.conversation.application;

import cn.aiworkbench.service.conversation.api.dto.ConversationResponse;
import cn.aiworkbench.service.conversation.api.dto.CreateConversationRequest;

import java.util.List;

public interface ConversationService {
    ConversationResponse createConversation(CreateConversationRequest request);
    List<ConversationResponse> listMine();

}
