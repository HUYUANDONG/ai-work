package cn.aiworkbench.service.conversation.application;

import lombok.Data;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 会话长期记忆槽位（结构化 LTM，非向量）。
 */
@Data
public class ConversationSessionState {

    private static final int MAX_EPISODES = 8;

    private String lastIntent;
    private Map<String, Object> lastTaskInput = new LinkedHashMap<>();
    private String activeTaskId;
    private boolean adviceOfferPending;
    private String goalMode;
    private Integer timeWindowDays;
    private Integer focusSlots;
    private String merchantId;
    private String lastReportTaskId;
    /** 旧轮 LLM 深度摘要（由 Python 高水位触发后回写）。 */
    private String workingSummary;
    /**
     * 摘要已覆盖到的最大 ai_message.id（含）。
     * 之后只把 id 更大的原文 + workingSummary 送给模型。
     */
    private Long summaryThroughMessageId;
    /** 已完成任务短摘要，新→旧最多 8 条。 */
    private List<Map<String, Object>> episodes = new ArrayList<>();

    /**
     * @return 可序列化副本
     */
    public Map<String, Object> toMap() {
        Map<String, Object> map = new LinkedHashMap<>();
        if (lastIntent != null && !lastIntent.isBlank()) {
            map.put("last_intent", lastIntent);
        }
        if (lastTaskInput != null && !lastTaskInput.isEmpty()) {
            map.put("last_task_input", new LinkedHashMap<>(lastTaskInput));
        }
        if (activeTaskId != null && !activeTaskId.isBlank()) {
            map.put("active_task_id", activeTaskId);
        }
        map.put("advice_offer_pending", adviceOfferPending);
        if (goalMode != null && !goalMode.isBlank()) {
            map.put("goal_mode", goalMode);
        }
        if (timeWindowDays != null) {
            map.put("time_window_days", timeWindowDays);
        }
        if (focusSlots != null) {
            map.put("focus_slots", focusSlots);
        }
        if (merchantId != null && !merchantId.isBlank()) {
            map.put("merchant_id", merchantId);
        }
        if (lastReportTaskId != null && !lastReportTaskId.isBlank()) {
            map.put("last_report_task_id", lastReportTaskId);
        }
        if (workingSummary != null && !workingSummary.isBlank()) {
            map.put("working_summary", workingSummary);
        }
        if (summaryThroughMessageId != null && summaryThroughMessageId > 0) {
            map.put("summary_through_message_id", summaryThroughMessageId);
        }
        if (episodes != null && !episodes.isEmpty()) {
            List<Map<String, Object>> copy = new ArrayList<>();
            for (Map<String, Object> ep : episodes) {
                if (ep != null) {
                    copy.add(new LinkedHashMap<>(ep));
                }
            }
            map.put("episodes", copy);
        }
        return map;
    }

    /**
     * @param raw JSON 反序列化后的 map
     * @return 状态
     */
    @SuppressWarnings("unchecked")
    public static ConversationSessionState fromMap(Map<String, Object> raw) {
        ConversationSessionState state = new ConversationSessionState();
        if (raw == null || raw.isEmpty()) {
            return state;
        }
        Object intent = raw.get("last_intent");
        if (intent != null && !String.valueOf(intent).isBlank()) {
            state.setLastIntent(String.valueOf(intent));
        }
        Object task = raw.get("last_task_input");
        if (task instanceof Map<?, ?> map) {
            state.setLastTaskInput(new LinkedHashMap<>((Map<String, Object>) map));
        }
        Object active = raw.get("active_task_id");
        if (active != null && !String.valueOf(active).isBlank()) {
            state.setActiveTaskId(String.valueOf(active));
        }
        Object offer = raw.get("advice_offer_pending");
        if (offer instanceof Boolean b) {
            state.setAdviceOfferPending(b);
        } else if (offer != null) {
            state.setAdviceOfferPending(Boolean.parseBoolean(String.valueOf(offer)));
        }
        if (!state.isAdviceOfferPending()
                && state.getLastTaskInput() != null
                && Boolean.TRUE.equals(state.getLastTaskInput().get("advice_offer_pending"))) {
            state.setAdviceOfferPending(true);
        }
        state.setGoalMode(asText(first(raw.get("goal_mode"), nested(state.getLastTaskInput(), "goal_mode"))));
        state.setTimeWindowDays(asInt(first(raw.get("time_window_days"), nested(state.getLastTaskInput(), "time_window_days"))));
        state.setFocusSlots(asInt(first(raw.get("focus_slots"), nested(state.getLastTaskInput(), "focus_slots"))));
        state.setMerchantId(asText(first(raw.get("merchant_id"), nested(state.getLastTaskInput(), "merchant_id"))));
        state.setLastReportTaskId(asText(raw.get("last_report_task_id")));
        state.setWorkingSummary(asText(raw.get("working_summary")));
        state.setSummaryThroughMessageId(asLong(raw.get("summary_through_message_id")));
        Object eps = raw.get("episodes");
        if (eps instanceof List<?> list) {
            List<Map<String, Object>> episodes = new ArrayList<>();
            for (Object item : list) {
                if (item instanceof Map<?, ?> m) {
                    episodes.add(new LinkedHashMap<>((Map<String, Object>) m));
                }
                if (episodes.size() >= MAX_EPISODES) {
                    break;
                }
            }
            state.setEpisodes(episodes);
        }
        return state;
    }

    /**
     * 追加一条任务 episode，保留最近 {@link #MAX_EPISODES} 条。
     *
     * @param episode 摘要
     */
    public void addEpisode(Map<String, Object> episode) {
        if (episode == null || episode.isEmpty()) {
            return;
        }
        if (episodes == null) {
            episodes = new ArrayList<>();
        }
        episodes.add(new LinkedHashMap<>(episode));
        if (episodes.size() > MAX_EPISODES) {
            episodes = new ArrayList<>(episodes.subList(episodes.size() - MAX_EPISODES, episodes.size()));
        }
    }

    private static Object first(Object a, Object b) {
        return a != null ? a : b;
    }

    private static Object nested(Map<String, Object> map, String key) {
        return map == null ? null : map.get(key);
    }

    private static String asText(Object value) {
        if (value == null) {
            return null;
        }
        String text = String.valueOf(value).trim();
        if (text.isEmpty() || "null".equalsIgnoreCase(text)) {
            return null;
        }
        return text;
    }

    private static Integer asInt(Object value) {
        if (value instanceof Number n) {
            return n.intValue();
        }
        String text = asText(value);
        if (text == null) {
            return null;
        }
        try {
            return Integer.parseInt(text);
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private static Long asLong(Object value) {
        if (value instanceof Number n) {
            return n.longValue();
        }
        String text = asText(value);
        if (text == null) {
            return null;
        }
        try {
            return Long.parseLong(text);
        } catch (NumberFormatException ex) {
            return null;
        }
    }
}
