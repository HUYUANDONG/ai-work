package cn.aiworkbench.service.conversation.api;

import cn.aiworkbench.service.conversation.sse.ConversationSseHub;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

/**
 * 会话思考流 / LLM token SSE。
 */
@Tag(name = "Conversation Stream")
@RestController
@RequestMapping("/api/v1/conversations")
@RequiredArgsConstructor
public class ConversationStreamController {

    private final ConversationSseHub sseHub;

    /**
     * 订阅会话事件（thinking / llm_delta / reply / done）。
     *
     * @param conversationId 会话 ID
     * @return SSE
     */
    @Operation(summary = "会话 SSE 流")
    @GetMapping(value = "/{conversationId}/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter stream(@PathVariable String conversationId) {
        return sseHub.subscribe(conversationId);
    }
}
