package cn.aiworkbench.service.conversation.sse;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * 会话级 SSE 扇出：任务进度 / LLM delta / 对话终态。
 */
@Slf4j
@Component
public class ConversationSseHub {

    private static final long TIMEOUT_MS = 0L;

    private final Map<String, CopyOnWriteArrayList<SseEmitter>> emitters = new ConcurrentHashMap<>();

    /**
     * 订阅某会话的事件流。
     *
     * @param conversationId 会话 ID
     * @return SseEmitter
     */
    public SseEmitter subscribe(String conversationId) {
        String key = normalize(conversationId);
        SseEmitter emitter = new SseEmitter(TIMEOUT_MS);
        CopyOnWriteArrayList<SseEmitter> bucket =
                emitters.computeIfAbsent(key, id -> new CopyOnWriteArrayList<>());
        bucket.add(emitter);
        Runnable cleanup = () -> {
            bucket.remove(emitter);
            if (bucket.isEmpty()) {
                emitters.remove(key, bucket);
            }
        };
        emitter.onCompletion(cleanup);
        emitter.onTimeout(cleanup);
        emitter.onError(ex -> cleanup.run());
        try {
            emitter.send(SseEmitter.event().name("ready").data(Map.of(
                    "conversation_id", key,
                    "ok", true
            )));
        } catch (IOException ex) {
            cleanup.run();
        }
        return emitter;
    }

    /**
     * 向订阅者推送命名事件。
     *
     * @param conversationId 会话
     * @param eventName      事件名 thinking / llm_delta / reply / done
     * @param payload        载荷
     */
    public void publish(String conversationId, String eventName, Object payload) {
        String key = normalize(conversationId);
        List<SseEmitter> bucket = emitters.get(key);
        if (bucket == null || bucket.isEmpty()) {
            return;
        }
        String name = eventName == null || eventName.isBlank() ? "message" : eventName;
        Object data = payload == null ? Map.of() : payload;
        for (SseEmitter emitter : bucket) {
            try {
                emitter.send(SseEmitter.event().name(name).data(data));
            } catch (Exception ex) {
                log.debug("sse send failed conversation={} event={}", key, name);
                try {
                    emitter.complete();
                } catch (Exception ignored) {
                    // ignore
                }
                bucket.remove(emitter);
            }
        }
        if (bucket.isEmpty()) {
            emitters.remove(key, bucket);
        }
    }

    /**
     * @param conversationId 原始 ID
     * @return 非空键
     */
    private static String normalize(String conversationId) {
        if (conversationId == null || conversationId.isBlank()) {
            return "c-unknown";
        }
        return conversationId.trim();
    }
}
