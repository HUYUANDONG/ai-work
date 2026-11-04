package cn.aiworkbench.service.integration.outfitadmin;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 把 goodsStatList 多日行聚合成 Agent 特征行。
 * <p>
 * 只下发打分/会签需要的字段：身份 + 品牌 + 窗口指标。
 * 清洗规则：去图片/链接/运营别名；标题截断；金额订单取整；转化率两位小数；
 * 元数据（amount_unit/source）不上每行，由响应信封承载。
 */
public final class GoodsStatSnapshotMapper {

    /** 会签/列表可读标题上限（中文电商标题常 40+ 字）。 */
    static final int TITLE_MAX = 36;

    private GoodsStatSnapshotMapper() {
    }

    /**
     * 按 goodsId 合并当前窗与对比窗。
     *
     * @param current  当前窗口原始行
     * @param previous 对比窗口原始行
     * @return 精简快照行
     */
    public static List<Map<String, Object>> mergeWindows(
            List<Map<String, Object>> current,
            List<Map<String, Object>> previous) {
        Map<String, Agg> curr = aggregate(current);
        Map<String, Agg> prev = aggregate(previous);
        Map<String, Agg> all = new LinkedHashMap<>(curr);
        prev.forEach(all::putIfAbsent);
        List<Map<String, Object>> rows = new ArrayList<>();
        for (Map.Entry<String, Agg> entry : all.entrySet()) {
            String id = entry.getKey();
            Agg now = curr.get(id);
            Agg before = prev.get(id);
            Agg ident = now != null ? now : before;
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("sku_id", String.valueOf(ident.goodsId));
            putIfPresent(row, "title", shortenTitle(ident.goodsName));
            // 品牌只留 gbName；供应商牌名会签用不到，去掉省字数
            putIfPresent(row, "brand", ident.gbName);
            row.put("on_sale", Boolean.TRUE);
            // 评分窗口：金额单位为元（运营接口 orderSales），整型避免 897.0 膨胀
            row.put("gmv_30d", whole(now == null ? 0D : now.orderSales));
            row.put("gmv_prev_30d", whole(before == null ? 0D : before.orderSales));
            row.put("orders_30d", whole(now == null ? 0D : now.orderNumbers));
            row.put("orders_prev_30d", whole(before == null ? 0D : before.orderNumbers));
            putIfPresent(row, "paid_orders_from_clicks_30d", now == null ? null : whole(now.orderPays));
            putIfPresent(row, "impressions_30d", now == null ? null : whole(now.goodsPv));
            putIfPresent(row, "impressions_prev_30d", before == null ? null : whole(before.goodsPv));
            putIfPresent(row, "clicks_30d", now == null ? null : whole(now.goodsUv));
            putIfPresent(row, "clicks_prev_30d", before == null ? null : whole(before.goodsUv));
            // 页面转化率（ratePer）取最近一次有值的展示值，不作多日加总
            Double rate = now != null && now.ratePer != null
                    ? now.ratePer
                    : (before == null ? null : before.ratePer);
            putIfPresent(row, "rate_per", rate == null ? null : round2(rate));
            rows.add(row);
        }
        return rows;
    }

    /**
     * 截断标题，超长加省略号。
     *
     * @param name 原始商品名
     * @return 短标题；空则 null
     */
    static String shortenTitle(Object name) {
        if (name == null) {
            return null;
        }
        String text = String.valueOf(name).trim().replaceAll("\\s+", " ");
        if (text.isEmpty()) {
            return null;
        }
        if (text.length() <= TITLE_MAX) {
            return text;
        }
        return text.substring(0, TITLE_MAX - 1) + "…";
    }

    private static long whole(double value) {
        return Math.round(value);
    }

    private static double round2(double value) {
        return Math.round(value * 100D) / 100D;
    }

    private static void putIfPresent(Map<String, Object> row, String key, Object value) {
        if (value != null) {
            row.put(key, value);
        }
    }

    private static Map<String, Agg> aggregate(List<Map<String, Object>> list) {
        Map<String, Agg> map = new LinkedHashMap<>();
        if (list == null) {
            return map;
        }
        for (Map<String, Object> raw : list) {
            if (raw == null || raw.get("goodsId") == null) {
                continue;
            }
            String id = String.valueOf(raw.get("goodsId"));
            Agg agg = map.computeIfAbsent(id, key -> new Agg());
            agg.goodsId = raw.get("goodsId");
            if (raw.get("goodsName") != null) {
                agg.goodsName = raw.get("goodsName");
            }
            if (raw.get("gbName") != null) {
                agg.gbName = raw.get("gbName");
            }
            agg.orderSales += toDouble(raw.get("orderSales"));
            agg.orderNumbers += toDouble(raw.get("orderNumbers"));
            agg.orderPays += toDouble(raw.get("orderPays"));
            agg.goodsPv += toDouble(raw.get("goodsPv"));
            agg.goodsUv += toDouble(raw.get("goodsUv"));
            if (raw.get("ratePer") != null) {
                agg.ratePer = toDouble(raw.get("ratePer"));
            }
        }
        return map;
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

    private static final class Agg {
        private Object goodsId;
        private Object goodsName;
        private Object gbName;
        private double orderSales;
        private double orderNumbers;
        private double orderPays;
        private double goodsPv;
        private double goodsUv;
        private Double ratePer;
    }
}
