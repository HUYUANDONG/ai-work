package cn.aiworkbench.service.persist;

import cn.aiworkbench.service.persist.mapper.AiExplosionMapper;
import cn.aiworkbench.service.persist.mapper.AiQualityMapper;
import cn.hutool.core.util.StrUtil;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 把爆品 / 质检报告写入 MySQL，并按会话回读（Java 重启后追问靠它）。
 *
 * <p>本类注解：
 * <ul>
 *   <li>{@code @Slf4j} — Lombok，生成 {@code log}。</li>
 *   <li>{@code @Service} — Spring。和 {@code @Component} 扫描方式相同，语义上表示「业务服务」。</li>
 *   <li>{@code @RequiredArgsConstructor} — Lombok。为三个 {@code final} 字段生成构造器，Spring 据此注入
 *       Mapper 和 {@link ObjectMapper}（Jackson，Spring Boot 默认已有一个 Bean）。</li>
 *   <li>{@code @ConditionalOnProperty} — Spring Boot（在 spring-boot 包，不是 spring-core）。
 *       只有 {@code wb.mysql.enabled=true} 时才创建本 Bean；关掉则整个落库链路不存在，
 *       上层用 {@code ObjectProvider.getIfAvailable()} 判断。</li>
 * </ul>
 */
@Slf4j
@Service
@RequiredArgsConstructor
@ConditionalOnProperty(name = "wb.mysql.enabled", havingValue = "true")
public class ReportPersistService {

    private final AiExplosionMapper explosionMapper;
    private final AiQualityMapper qualityMapper;
    private final ObjectMapper objectMapper;

    /**
     * 覆盖写入报告。爆品走 {@code ai_explosion_analysis} + {@code ai_explosion_item}。
     *
     * <p>{@code @Transactional} — Spring 事务（spring-tx）。方法里多条 SQL 要么全成功要么全回滚，
     * 避免「头写入了、商品行删了一半」的半成品。关 MySQL 时本类根本不会进容器，这条注解也不会生效。
     *
     * @param taskId         任务
     * @param taskType       {@code EXPLOSION} / {@code QUALITY}
     * @param conversationId 会话
     * @param userId         用户
     * @param header         报告头
     * @param items          SKU 行
     */
    @Transactional
    public void upsert(
            String taskId,
            String taskType,
            String conversationId,
            String userId,
            Map<String, Object> header,
            List<?> items) {
        if (StrUtil.isBlank(taskId)) {
            return;
        }
        Map<String, Object> head = header == null ? Map.of() : header;
        if ("QUALITY".equalsIgnoreCase(taskType)) {
            writeQuality(taskId, conversationId, userId, head, items);
        } else {
            writeExplosion(taskId, conversationId, userId, head, items);
        }
    }

    /**
     * 从库组装会话报告（新→旧），结构和内存仓相同，方便 Controller 无感切换。
     *
     * @param conversationId 会话
     * @param userId         用户
     * @param limit          条数
     * @return 报告列表
     */
    public List<Map<String, Object>> listByConversation(String conversationId, String userId, int limit) {
        if (StrUtil.isBlank(conversationId) || StrUtil.isBlank(userId)) {
            return List.of();
        }
        int cap = Math.min(Math.max(limit, 1), 20);
        List<Map<String, Object>> out = new ArrayList<>();
        for (Map<String, Object> row : explosionMapper.listHeaders(conversationId, userId, cap)) {
            out.add(toExplosionEntry(row));
        }
        for (Map<String, Object> row : qualityMapper.listHeaders(conversationId, userId, cap)) {
            out.add(toQualityEntry(row));
        }
        out.sort(Comparator.comparing(this::createdAt, Comparator.nullsLast(Comparator.reverseOrder())));
        if (out.size() > cap) {
            return new ArrayList<>(out.subList(0, cap));
        }
        return out;
    }

    /**
     * 先 upsert 报告头，再删旧行、逐条插入 SKU。调用方已在事务里。
     *
     * @param taskId         任务
     * @param conversationId 会话
     * @param userId         用户
     * @param header         头字段
     * @param items          SKU 列表
     */
    private void writeExplosion(
            String taskId,
            String conversationId,
            String userId,
            Map<String, Object> header,
            List<?> items) {
        explosionMapper.upsertHeader(
                taskId,
                userId,
                conversationId,
                text(header.get("snapshot_date")),
                text(header.get("scoring_version")),
                text(header.get("council_version")),
                asInt(header.get("time_window_days")),
                asInt(header.get("top_n")),
                asInt(header.get("item_count")),
                text(header.get("goal_mode")),
                asInt(header.get("focus_slots")),
                bool01(header.get("plan_degraded")),
                asInt(header.get("focus_count")),
                text(header.get("summary")),
                json(header));
        explosionMapper.deleteItems(taskId);
        int rank = 1;
        for (Object raw : items == null ? List.of() : items) {
            // instanceof Map<?, ?> map 是 JDK16+ 模式匹配：判断类型同时声明变量 map
            if (!(raw instanceof Map<?, ?> map)) {
                continue;
            }
            @SuppressWarnings("unchecked")
            Map<String, Object> item = (Map<String, Object>) map;
            String sku = text(first(item.get("sku_id"), item.get("goodsId")));
            if (StrUtil.isBlank(sku)) {
                continue;
            }
            Integer rankNo = asInt(first(item.get("rank_no"), item.get("rank")));
            explosionMapper.upsertItem(
                    taskId,
                    sku,
                    rankNo == null ? rank : rankNo,
                    asDouble(item.get("explosion_score")),
                    text(item.get("action_bucket")),
                    text(item.get("primary_action")),
                    bool01(item.get("in_focus_slot")),
                    text(item.get("quality_risk_level")),
                    json(item.get("feature_excerpt")),
                    json(first(item.get("council_excerpt"), item.get("council"))),
                    text(first(item.get("ai_reason"), item.get("rationale"))));
            rank++;
        }
    }

    /**
     * 质检报告写入（同事务约定）。
     *
     * @param taskId         任务
     * @param conversationId 会话
     * @param userId         用户
     * @param header         头
     * @param items          SKU
     */
    private void writeQuality(
            String taskId,
            String conversationId,
            String userId,
            Map<String, Object> header,
            List<?> items) {
        qualityMapper.upsertHeader(
                taskId,
                userId,
                conversationId,
                text(header.get("snapshot_date")),
                text(header.get("scoring_version")),
                asInt(header.get("sku_count")),
                asInt(header.get("high_risk_count")),
                text(header.get("summary")),
                json(header));
        qualityMapper.deleteItems(taskId);
        for (Object raw : items == null ? List.of() : items) {
            if (!(raw instanceof Map<?, ?> map)) {
                continue;
            }
            @SuppressWarnings("unchecked")
            Map<String, Object> item = (Map<String, Object>) map;
            String sku = text(item.get("sku_id"));
            if (StrUtil.isBlank(sku)) {
                continue;
            }
            Boolean cand = asBool(item.get("explosion_candidate"));
            qualityMapper.upsertItem(
                    taskId,
                    sku,
                    asDouble(item.get("quality_score")),
                    asDouble(item.get("ops_score")),
                    text(item.get("risk_level")),
                    asDouble(item.get("explosion_score")),
                    cand == null ? null : (cand ? 1 : 0),
                    json(item.get("issues")),
                    json(item.get("skipped_rules")),
                    json(item.get("feature_excerpt")));
        }
    }

    /**
     * 把库里的爆品头 + 行，收成和内存仓一样的 entry。
     *
     * @param row {@code ai_explosion_analysis} 一行
     * @return 报告
     */
    private Map<String, Object> toExplosionEntry(Map<String, Object> row) {
        String taskId = text(col(row, "task_id", "taskId"));
        Map<String, Object> header = parseJsonMap(col(row, "header_json", "headerJson"));
        if (header.isEmpty()) {
            header = new LinkedHashMap<>();
            header.put("task_id", taskId);
            header.put("summary", col(row, "summary", "summary"));
            header.put("goal_mode", col(row, "goal_mode", "goalMode"));
        }
        Map<String, Object> entry = new LinkedHashMap<>();
        entry.put("task_id", taskId);
        entry.put("task_type", "EXPLOSION");
        entry.put("created_at", String.valueOf(col(row, "created_at", "createdAt")));
        entry.put("header", header);
        entry.put("items", normalizeExplosionItems(explosionMapper.listItems(taskId)));
        return entry;
    }

    /**
     * 质检头 + 行 → 统一 entry。
     *
     * @param row {@code ai_quality_inspection} 一行
     * @return 报告
     */
    private Map<String, Object> toQualityEntry(Map<String, Object> row) {
        String taskId = text(col(row, "task_id", "taskId"));
        Map<String, Object> header = parseJsonMap(col(row, "header_json", "headerJson"));
        if (header.isEmpty()) {
            header = new LinkedHashMap<>();
            header.put("task_id", taskId);
            header.put("summary", col(row, "summary", "summary"));
        }
        Map<String, Object> entry = new LinkedHashMap<>();
        entry.put("task_id", taskId);
        entry.put("task_type", "QUALITY");
        entry.put("created_at", String.valueOf(col(row, "created_at", "createdAt")));
        entry.put("header", header);
        entry.put("items", normalizeQualityItems(qualityMapper.listItems(taskId)));
        return entry;
    }

    /**
     * 列名兼容：MyBatis 有时给蛇形，有时给驼峰。
     *
     * @param rows 商品行
     * @return 契约字段
     */
    private List<Map<String, Object>> normalizeExplosionItems(List<Map<String, Object>> rows) {
        List<Map<String, Object>> out = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("sku_id", col(row, "sku_id", "skuId"));
            item.put("rank_no", col(row, "rank_no", "rankNo"));
            item.put("explosion_score", col(row, "explosion_score", "explosionScore"));
            item.put("action_bucket", col(row, "action_bucket", "actionBucket"));
            item.put("primary_action", col(row, "primary_action", "primaryAction"));
            item.put("in_focus_slot", bool01(col(row, "in_focus_slot", "inFocusSlot")) == 1);
            item.put("quality_risk_level", col(row, "quality_risk_level", "qualityRiskLevel"));
            item.put("feature_excerpt", parseJson(col(row, "feature_excerpt", "featureExcerpt")));
            item.put("council_excerpt", parseJson(col(row, "council_excerpt", "councilExcerpt")));
            item.put("ai_reason", col(row, "ai_reason", "aiReason"));
            out.add(item);
        }
        return out;
    }

    /**
     * 质检行字段对齐。
     *
     * @param rows 库行
     * @return 契约字段
     */
    private List<Map<String, Object>> normalizeQualityItems(List<Map<String, Object>> rows) {
        List<Map<String, Object>> out = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("sku_id", col(row, "sku_id", "skuId"));
            item.put("quality_score", col(row, "quality_score", "qualityScore"));
            item.put("ops_score", col(row, "ops_score", "opsScore"));
            item.put("risk_level", col(row, "risk_level", "riskLevel"));
            item.put("explosion_score", col(row, "explosion_score", "explosionScore"));
            item.put("explosion_candidate", bool01(col(row, "explosion_candidate", "explosionCandidate")) == 1);
            item.put("issues", parseJson(col(row, "issues_json", "issuesJson")));
            item.put("skipped_rules", parseJson(col(row, "skipped_rules", "skippedRules")));
            item.put("feature_excerpt", parseJson(col(row, "feature_excerpt", "featureExcerpt")));
            out.add(item);
        }
        return out;
    }

    /**
     * 排序键：创建时间字符串。
     *
     * @param entry 报告
     * @return created_at
     */
    private String createdAt(Map<String, Object> entry) {
        Object v = entry.get("created_at");
        return v == null ? "" : String.valueOf(v);
    }

    /**
     * 第一个非 null。
     *
     * @param a 优先
     * @param b 回落
     * @return a 或 b
     */
    private static Object first(Object a, Object b) {
        return a != null ? a : b;
    }

    /**
     * 同时兼容蛇形 / 驼峰列名。
     *
     * @param row   一行
     * @param snake snake_case
     * @param camel camelCase
     * @return 值
     */
    private static Object col(Map<String, Object> row, String snake, String camel) {
        if (row.containsKey(snake)) {
            return row.get(snake);
        }
        return row.get(camel);
    }

    /**
     * 空串 / {@code "null"} 都当成没有。
     *
     * @param value 任意
     * @return 文本或 null
     */
    private static String text(Object value) {
        if (value == null) {
            return null;
        }
        String text = String.valueOf(value).trim();
        return text.isEmpty() || "null".equalsIgnoreCase(text) ? null : text;
    }

    /**
     * 宽松转 Integer。{@code instanceof Number n} 也是 JDK 模式匹配。
     *
     * @param value 数字或数字字符串
     * @return 整数或 null
     */
    private static Integer asInt(Object value) {
        if (value instanceof Number n) {
            return n.intValue();
        }
        String text = text(value);
        if (text == null) {
            return null;
        }
        try {
            return Integer.parseInt(text);
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    /**
     * 宽松转 Double。
     *
     * @param value 数字或数字字符串
     * @return 浮点或 null
     */
    private static Double asDouble(Object value) {
        if (value instanceof Number n) {
            return n.doubleValue();
        }
        String text = text(value);
        if (text == null) {
            return null;
        }
        try {
            return Double.parseDouble(text);
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    /**
     * true/1/"true" 视为真。
     *
     * @param value 布尔或数字或字符串
     * @return 布尔或 null
     */
    private static Boolean asBool(Object value) {
        if (value instanceof Boolean b) {
            return b;
        }
        if (value instanceof Number n) {
            return n.intValue() != 0;
        }
        String text = text(value);
        if (text == null) {
            return null;
        }
        return "true".equalsIgnoreCase(text) || "1".equals(text);
    }

    /**
     * 落库用 0/1，缺省 0。
     *
     * @param value 布尔类
     * @return 1 或 0
     */
    private static int bool01(Object value) {
        Boolean b = asBool(value);
        return Boolean.TRUE.equals(b) ? 1 : 0;
    }

    /**
     * 任意对象 → JSON 字符串。{@link ObjectMapper} 是 Jackson（Spring Boot 自带 starter，不是 JDK）。
     *
     * @param value 对象
     * @return JSON 或 null
     */
    private String json(Object value) {
        if (value == null) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(value);
        } catch (Exception ex) {
            log.warn("serialize report json failed", ex);
            return null;
        }
    }

    /**
     * JSON 对象字符串 → Map。
     *
     * @param raw 库字段
     * @return Map；解析失败则空 Map
     */
    private Map<String, Object> parseJsonMap(Object raw) {
        Object parsed = parseJson(raw);
        if (parsed instanceof Map<?, ?> map) {
            Map<String, Object> out = new LinkedHashMap<>();
            map.forEach((k, v) -> out.put(String.valueOf(k), v));
            return out;
        }
        return new LinkedHashMap<>();
    }

    /**
     * {@code TypeReference<>() {}} 是 Jackson 的匿名子类写法，用来保留 {@code Map/List} 的泛型，
     * 普通 {@code readValue(s, Map.class)} 会丢掉 value 类型。
     *
     * @param raw 已是对象则原样返回；字符串则 parse
     * @return 解析结果
     */
    private Object parseJson(Object raw) {
        if (raw == null) {
            return null;
        }
        if (!(raw instanceof String s) || s.isBlank()) {
            return raw;
        }
        try {
            return objectMapper.readValue(s, new TypeReference<>() {});
        } catch (Exception ex) {
            return s;
        }
    }
}
