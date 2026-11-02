package cn.aiworkbench.service.conversation.api;

import cn.aiworkbench.common.web.api.ApiResult;
import cn.aiworkbench.service.conversation.api.dto.ConversationResponse;
import cn.aiworkbench.service.conversation.api.dto.CreateConversationRequest;

import cn.aiworkbench.service.conversation.application.ConversationService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@Tag(name = "Conversation")
@RestController
@RequestMapping("/api/v1/conversations")
@RequiredArgsConstructor
public class ConversationController {

    private final ConversationService conversationService;

    @Operation(summary = "新建对话")
    @PostMapping("/create")
    public ApiResult<ConversationResponse> createConversation(
            @RequestBody(required = false) CreateConversationRequest request) {
        return ApiResult.ok(conversationService.createConversation(request));
    }

    @Operation(summary = "查询对话")
    @GetMapping("/list")
    public ApiResult<List<ConversationResponse>> listMine() {
        return ApiResult.ok(conversationService.listMine());
    }
}
