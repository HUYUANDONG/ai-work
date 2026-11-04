package cn.aiworkbench.service.integration.outfitadmin;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 把日板块 / 日流量大盘原始行压成 Agent 建议阶段字段。
 */
public final class AdviseContextMapper {

    private AdviseContextMapper() {
    }

    /**
     * 板块流量精简；按 selfUv 降序，最多 {@code limit} 条。
     *
     * @param raw   dailyPlateList 原始行
     * @param limit 上限
     * @return 精简行
     */
    public static List<Map<String, Object>> slimPlates(List<Map<String, Object>> raw, int limit) {
        List<Map<String, Object>> out = new ArrayList<>();
        if (raw == null) {
            return out;
        }
        List<Map<String, Object>> sorted = new ArrayList<>(raw);
        sorted.sort(Comparator.comparingDouble((Map<String, Object> row) -> toDouble(row.get("selfUv"))).reversed());
        int cap = Math.max(1, Math.min(limit, 20));
        for (Map<String, Object> row : sorted) {
            if (out.size() >= cap) {
                break;
            }
            if (row == null || row.get("statField") == null) {
                continue;
            }
            Map<String, Object> slim = new LinkedHashMap<>();
            slim.put("stat_field", row.get("statField"));
            slim.put("stat_field_name", row.get("statFieldName"));
            slim.put("self_pv", toDouble(row.get("selfPv")));
            slim.put("self_uv", toDouble(row.get("selfUv")));
            slim.put("order_sales", toDouble(row.get("orderSales")));
            slim.put("order_numbers", toDouble(row.get("orderNumbers")));
            if (row.get("statDay") != null) {
                slim.put("stat_day", row.get("statDay"));
            }
            out.add(slim);
        }
        return out;
    }

    /**
     * 取大盘最近一行摘要。
     *
     * @param raw dailyDataList 原始行
     * @return 摘要或空 Map
     */
    public static Map<String, Object> slimStore(List<Map<String, Object>> raw) {
        if (raw == null || raw.isEmpty()) {
            return Map.of();
        }
        Map<String, Object> last = raw.get(raw.size() - 1);
        if (last == null) {
            return Map.of();
        }
        Map<String, Object> slim = new LinkedHashMap<>();
        put(slim, "total_sales", last.get("totalSales"));
        put(slim, "order_numbers", last.get("orderNumbers"));
        put(slim, "hpage_uv", last.get("hpageUv"));
        put(slim, "spu_uv", last.get("spuUv"));
        put(slim, "spu_pv", last.get("spuPv"));
        put(slim, "conversion_rate", last.get("conversionRate"));
        put(slim, "stat_day", last.get("statDay"));
        return slim;
    }

    private static void put(Map<String, Object> target, String key, Object value) {
        if (value != null) {
            target.put(key, value);
        }
    }

    private static double toDouble(Object value) {
        if (value == null) {
            return 0D;
        }
        if (value instanceof Number number) {
            return number.doubleValue();
        }
        try {
            return Double.parseDouble(String.valueOf(value));
        } catch (NumberFormatException ex) {
            return 0D;
        }
    }
}
