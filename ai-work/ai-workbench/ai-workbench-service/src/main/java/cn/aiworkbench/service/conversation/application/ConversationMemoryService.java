package cn.aiworkbench.service.conversation.application;

import cn.aiworkbench.service.conversation.infra.AiConversationDO;
import cn.aiworkbench.service.conversation.infra.AiMessageDO;
import cn.aiworkbench.service.conversation.mapper.AiConversationMapper;
import cn.aiworkbench.service.conversation.mapper.AiMessageMapper;
import cn.hutool.core.util.StrUtil;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 对话记忆持久化：短窗消息 + 结构化 LTM 槽位（MySQL）。
 */
@Slf4j
@Service
@RequiredArgsConstructor
@ConditionalOnProperty(name = "wb.mysql.enabled", havingValue = "true")
public class ConversationMemoryService {

    private final AiConversationMapper conversationMapper;
    private final AiMessageMapper messageMapper;
    private final ObjectMapper objectMapper;

    /**
     * 确保会话行存在。
     *
     * @param conversationId 对外会话 ID
     * @param userId         用户
     * @param titleHint      可选标题
     */
    public void ensureConversation(String conversationId, String userId, String titleHint) {
        if (StrUtil.isBlank(conversationId) || StrUtil.isBlank(userId)) {
            return;
        }
        AiConversationDO existing = conversationMapper.selectByConversationId(conversationId);
        if (existing != null) {
            return;
        }
        AiConversationDO row = new AiConversationDO();
        row.setConversationId(conversationId);
        row.setUserId(userId);
        row.setTitle(StrUtil.blankToDefault(titleHint, "新对话"));
        row.setSessionStateJson(null);
        conversationMapper.insertIgnore(row);
    }

    /**
     * 读取 LTM 槽位。
     *
     * @param conversationId 会话
     * @return 状态（永不为 null）
     */
    public ConversationSessionState loadState(String conversationId) {
        if (StrUtil.isBlank(conversationId)) {
            return new ConversationSessionState();
        }
        AiConversationDO row = conversationMapper.selectByConversationId(conversationId);
        if (row == null || StrUtil.isBlank(row.getSessionStateJson())) {
            return new ConversationSessionState();
        }
        try {
            Map<String, Object> map = objectMapper.readValue(
                    row.getSessionStateJson(), new TypeReference<>() {});
            return ConversationSessionState.fromMap(map);
        } catch (Exception ex) {
            log.warn("parse session_state_json failed conversationId={}", conversationId, ex);
            return new ConversationSessionState();
        }
    }

    /**
     * 写入 LTM 槽位。
     *
     * @param conversationId 会话
     * @param state          状态
     */
    public void saveState(String conversationId, ConversationSessionState state) {
        if (StrUtil.isBlank(conversationId) || state == null) {
            return;
        }
        try {
            String json = objectMapper.writeValueAsString(state.toMap());
            conversationMapper.updateSessionState(conversationId, json);
        } catch (Exception ex) {
            log.warn("save session_state_json failed conversationId={}", conversationId, ex);
        }
    }

    /**
     * 最近 N 条消息，格式与 Python history 一致（旧→新）。
     *
     * @param conversationId 会话
     * @param limit          条数
     * @return history 元素
     */
    public List<Map<String, Object>> recentHistory(String conversationId, int limit) {
        if (StrUtil.isBlank(conversationId) || limit <= 0) {
            return List.of();
        }
        return toHistoryItems(messageMapper.selectRecent(conversationId, limit));
    }

    /**
     * 摘要水位之后的原文历史（旧→新）。有摘要时应用这个，避免把已压缩原文再塞进模型。
     *
     * @param conversationId 会话
     * @param afterId        已摘要覆盖到的最大消息 id（该 id 及更早的只靠 summary）
     * @param limit          条数上限
     * @return history 元素（含 id）
     */
    public List<Map<String, Object>> historyAfterSummary(
            String conversationId, long afterId, int limit) {
        if (StrUtil.isBlank(conversationId) || limit <= 0 || afterId <= 0) {
            return List.of();
        }
        return toHistoryItems(messageMapper.selectAfterId(conversationId, afterId, limit));
    }

    private static List<Map<String, Object>> toHistoryItems(List<AiMessageDO> rows) {
        List<Map<String, Object>> out = new ArrayList<>(rows.size());
        for (AiMessageDO row : rows) {
            Map<String, Object> item = new LinkedHashMap<>();
            if (row.getId() != null) {
                item.put("id", row.getId());
            }
            item.put("role", row.getRole());
            item.put("content", row.getContent() == null ? "" : row.getContent());
            if (StrUtil.isNotBlank(row.getIntent())) {
                item.put("intent", row.getIntent());
            }
            out.add(item);
        }
        return out;
    }

    /**
     * 落一条消息并刷新会话时间。
     *
     * @param conversationId 会话
     * @param userId         用户
     * @param role           user/assistant
     * @param content        正文
     * @param intent         可选意图
     * @param taskId         可选任务
     */
    @Transactional
    public void appendMessage(
            String conversationId,
            String userId,
            String role,
            String content,
            String intent,
            String taskId) {
        if (StrUtil.isBlank(conversationId) || StrUtil.isBlank(userId) || StrUtil.isBlank(role)) {
            return;
        }
        AiMessageDO row = new AiMessageDO();
        row.setConversationId(conversationId);
        row.setUserId(userId);
        row.setRole(role);
        row.setContent(content == null ? "" : content);
        row.setIntent(StrUtil.blankToDefault(intent, null));
        row.setTaskId(StrUtil.blankToDefault(taskId, null));
        row.setStreamInterrupted(false);
        messageMapper.insert(row);
        conversationMapper.touch(conversationId);
    }

    /**
     * 当前用户会话列表。
     *
     * @param userId 用户
     * @return 会话摘要
     */
    public List<Map<String, Object>> listConversations(String userId) {
        if (StrUtil.isBlank(userId)) {
            return List.of();
        }
        List<AiConversationDO> rows = conversationMapper.selectByUserId(userId);
        List<Map<String, Object>> out = new ArrayList<>(rows.size());
        for (AiConversationDO row : rows) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("conversation_id", row.getConversationId());
            item.put("title", StrUtil.blankToDefault(row.getTitle(), "新对话"));
            item.put("created_at", row.getCreatedAt() == null ? null : row.getCreatedAt().toString());
            item.put("updated_at", row.getUpdatedAt() == null ? null : row.getUpdatedAt().toString());
            out.add(item);
        }
        return out;
    }

    /**
     * 会话消息列表（旧→新）。
     *
     * @param conversationId 会话
     * @param userId         用户（校验归属）
     * @param limit          上限
     * @return 消息
     */
    public List<Map<String, Object>> listMessages(String conversationId, String userId, int limit) {
        if (StrUtil.isBlank(conversationId)) {
            return List.of();
        }
        AiConversationDO conv = conversationMapper.selectByConversationId(conversationId);
        if (conv == null) {
            return List.of();
        }
        if (StrUtil.isNotBlank(userId) && !userId.equals(conv.getUserId())) {
            return List.of();
        }
        int cap = Math.min(Math.max(limit, 1), 500);
        List<AiMessageDO> rows = messageMapper.selectByConversationId(conversationId, cap);
        List<Map<String, Object>> out = new ArrayList<>(rows.size());
        for (AiMessageDO row : rows) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", row.getId() == null ? null : String.valueOf(row.getId()));
            item.put("role", row.getRole());
            item.put("content", row.getContent() == null ? "" : row.getContent());
            if (StrUtil.isNotBlank(row.getIntent())) {
                item.put("intent", row.getIntent());
            }
            if (StrUtil.isNotBlank(row.getTaskId())) {
                item.put("task_id", row.getTaskId());
            }
            item.put("created_at", row.getCreatedAt() == null ? null : row.getCreatedAt().toString());
            out.add(item);
        }
        return out;
    }

    /**
     * 更新标题。
     *
     * @param conversationId 会话
     * @param title          标题
     */
    public void updateTitle(String conversationId, String title) {
        if (StrUtil.isBlank(conversationId) || StrUtil.isBlank(title)) {
            return;
        }
        conversationMapper.updateTitle(conversationId, StrUtil.maxLength(title, 200));
    }

    /**
     * 仅当标题仍是默认「新对话」时更新。
     *
     * @param conversationId 会话
     * @param title          新标题
     */
    public void updateTitleIfDefault(String conversationId, String title) {
        if (StrUtil.isBlank(conversationId) || StrUtil.isBlank(title)) {
            return;
        }
        AiConversationDO row = conversationMapper.selectByConversationId(conversationId);
        if (row == null) {
            return;
        }
        String current = StrUtil.blankToDefault(row.getTitle(), "新对话");
        if (!"新对话".equals(current)) {
            return;
        }
        conversationMapper.updateTitle(conversationId, StrUtil.maxLength(title, 200));
    }

    /**
     * 删除会话及其消息。
     *
     * @param conversationId 会话
     * @param userId         用户
     */
    @Transactional
    public void deleteConversation(String conversationId, String userId) {
        if (StrUtil.isBlank(conversationId) || StrUtil.isBlank(userId)) {
            return;
        }
        messageMapper.deleteByConversationId(conversationId);
        conversationMapper.deleteByConversationId(conversationId, userId);
    }

    /**
     * 导入历史消息（仅当库中尚无消息时，用于 localStorage 迁移）。
     *
     * @param conversationId 会话
     * @param userId         用户
     * @param title          标题
     * @param messages       [{role, content, intent?}]
     * @return 写入条数
     */
    @Transactional
    public int importMessagesIfEmpty(
            String conversationId,
            String userId,
            String title,
            List<Map<String, Object>> messages) {
        if (StrUtil.isBlank(conversationId) || StrUtil.isBlank(userId)) {
            return 0;
        }
        ensureConversation(conversationId, userId, title);
        if (messageMapper.countByConversationId(conversationId) > 0) {
            return 0;
        }
        if (messages == null || messages.isEmpty()) {
            return 0;
        }
        int written = 0;
        for (Map<String, Object> raw : messages) {
            if (raw == null) {
                continue;
            }
            String role = String.valueOf(raw.getOrDefault("role", "")).trim();
            if (!"user".equals(role) && !"assistant".equals(role)) {
                continue;
            }
            Object contentObj = raw.get("content");
            String content = contentObj == null ? "" : String.valueOf(contentObj);
            if (content.isBlank()) {
                continue;
            }
            Object intentObj = raw.get("intent");
            String intent = intentObj == null ? null : String.valueOf(intentObj);
            appendMessage(conversationId, userId, role, content, intent, null);
            written++;
        }
        if (StrUtil.isNotBlank(title) && !"新对话".equals(title)) {
            updateTitle(conversationId, title);
        }
        return written;
    }

    /**
     * 当前会话记忆快照（槽位 + 摘要 + episode）。
     *
     * @param conversationId 会话
     * @param userId         用户
     * @return 快照；无权限或无会话为空 map
     */
    public Map<String, Object> memorySnapshot(String conversationId, String userId) {
        if (StrUtil.isBlank(conversationId)) {
            return Map.of();
        }
        AiConversationDO conv = conversationMapper.selectByConversationId(conversationId);
        if (conv == null) {
            return Map.of();
        }
        if (StrUtil.isNotBlank(userId) && !userId.equals(conv.getUserId())) {
            return Map.of();
        }
        ConversationSessionState state = loadState(conversationId);
        Map<String, Object> out = new LinkedHashMap<>(state.toMap());
        out.put("conversation_id", conversationId);
        out.put("title", StrUtil.blankToDefault(conv.getTitle(), "新对话"));
        return out;
    }

    /**
     * 清空槽位 / 摘要 / episode，保留消息正文。
     *
     * @param conversationId 会话
     * @param userId         用户
     */
    public void clearMemory(String conversationId, String userId) {
        if (StrUtil.isBlank(conversationId) || StrUtil.isBlank(userId)) {
            return;
        }
        AiConversationDO conv = conversationMapper.selectByConversationId(conversationId);
        if (conv == null || !userId.equals(conv.getUserId())) {
            return;
        }
        saveState(conversationId, new ConversationSessionState());
    }
}
