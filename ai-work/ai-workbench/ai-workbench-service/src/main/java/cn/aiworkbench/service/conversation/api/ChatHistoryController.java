package cn.aiworkbench.service.conversation.api;

import cn.aiworkbench.common.core.error.CommonErrorCode;
import cn.aiworkbench.common.core.exception.BizException;
import cn.aiworkbench.common.security.identity.IdentityContext;
import cn.aiworkbench.common.web.api.ApiResult;
import cn.aiworkbench.service.conversation.application.ConversationMemoryService;
import cn.hutool.core.util.StrUtil;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * 对话历史落库 API（ai_conversation / ai_message）。
 */
@Tag(name = "Chat History")
@RestController
@RequestMapping("/api/v1/chat/conversations")
@RequiredArgsConstructor
@ConditionalOnBean(ConversationMemoryService.class)
public class ChatHistoryController {

    private final ConversationMemoryService memoryService;

    /**
     * 当前用户会话列表。
     *
     * @return 会话摘要
     */
    @Operation(summary = "列出我的会话（MySQL）")
    @GetMapping
    public ApiResult<List<Map<String, Object>>> listMine() {
        return ApiResult.ok(memoryService.listConversations(requireUserId()));
    }

    /**
     * 新建空会话。
     *
     * @param body 可选 conversation_id / title
     * @return 会话
     */
    @Operation(summary = "新建会话（写入 ai_conversation）")
    @PostMapping
    public ApiResult<Map<String, Object>> create(@RequestBody(required = false) Map<String, Object> body) {
        Map<String, Object> req = body == null ? Map.of() : body;
        String userId = requireUserId();
        String conversationId = String.valueOf(req.getOrDefault("conversation_id", "")).trim();
        if (conversationId.isEmpty() || "null".equalsIgnoreCase(conversationId)) {
            conversationId = "c-" + UUID.randomUUID().toString().replace("-", "").substring(0, 16);
        }
        String title = String.valueOf(req.getOrDefault("title", "新对话")).trim();
        if (title.isEmpty() || "null".equalsIgnoreCase(title)) {
            title = "新对话";
        }
        memoryService.ensureConversation(conversationId, userId, title);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("conversation_id", conversationId);
        out.put("title", title);
        return ApiResult.ok(out);
    }

    /**
     * 拉会话消息。
     *
     * @param conversationId 会话
     * @param limit          上限
     * @return 消息
     */
    @Operation(summary = "会话消息列表")
    @GetMapping("/{conversationId}/messages")
    public ApiResult<List<Map<String, Object>>> messages(
            @PathVariable String conversationId,
            @RequestParam(defaultValue = "200") int limit) {
        return ApiResult.ok(memoryService.listMessages(conversationId, requireUserId(), limit));
    }

    /**
     * 把浏览器本地历史导入库（仅库空时写入）。
     *
     * @param conversationId 会话
     * @param body           title + messages
     * @return 写入条数
     */
    @Operation(summary = "导入本地历史到 MySQL（仅空会话）")
    @PostMapping("/{conversationId}/import")
    public ApiResult<Map<String, Object>> importLocal(
            @PathVariable String conversationId,
            @RequestBody Map<String, Object> body) {
        String userId = requireUserId();
        String title = body == null ? "新对话" : String.valueOf(body.getOrDefault("title", "新对话"));
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> messages = body != null && body.get("messages") instanceof List<?> list
                ? (List<Map<String, Object>>) list
                : List.of();
        int written = memoryService.importMessagesIfEmpty(conversationId, userId, title, messages);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("conversation_id", conversationId);
        out.put("imported", written);
        return ApiResult.ok(out);
    }

    /**
     * 删除会话。
     *
     * @param conversationId 会话
     * @return ok
     */
    @Operation(summary = "删除会话及消息")
    @DeleteMapping("/{conversationId}")
    public ApiResult<Map<String, Object>> delete(@PathVariable String conversationId) {
        memoryService.deleteConversation(conversationId, requireUserId());
        return ApiResult.ok(Map.of("ok", true, "conversation_id", conversationId));
    }

    /**
     * 查看会话记忆槽位。
     *
     * @param conversationId 会话
     * @return 槽位 / 摘要 / episode
     */
    @Operation(summary = "查看会话记忆")
    @GetMapping("/{conversationId}/memory")
    public ApiResult<Map<String, Object>> memory(@PathVariable String conversationId) {
        return ApiResult.ok(memoryService.memorySnapshot(conversationId, requireUserId()));
    }

    /**
     * 清空槽位与 episode，不删聊天正文。
     *
     * @param conversationId 会话
     * @return ok
     */
    @Operation(summary = "清空会话记忆槽位")
    @DeleteMapping("/{conversationId}/memory")
    public ApiResult<Map<String, Object>> clearMemory(@PathVariable String conversationId) {
        memoryService.clearMemory(conversationId, requireUserId());
        return ApiResult.ok(Map.of("ok", true, "conversation_id", conversationId));
    }

    private static String requireUserId() {
        String userId = IdentityContext.userId();
        if (StrUtil.isBlank(userId)) {
            throw new BizException(CommonErrorCode.UNAUTHORIZED, "未登录");
        }
        return userId;
    }
}
