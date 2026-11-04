package cn.aiworkbench.service.integration.outfitadmin;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 特征行只保留 Agent 需要的字段。
 */
class GoodsStatSnapshotMapperTest {

    @Test
    void mergeWindowsKeepsLeanAgentFieldsOnly() {
        List<Map<String, Object>> current = List.of(Map.of(
                "goodsId", 1001,
                "goodsName", "测试鞋",
                "goodsFirstPic", "https://example.com/a.jpg",
                "goodsLink", "http://example.com/goods?id=1001",
                "gbName", "测试牌",
                "supBrandName", "供应商",
                "orderSales", 100,
                "orderNumbers", 2,
                "orderPays", 2,
                "goodsPv", 50,
                "goodsUv", 20,
                "ratePer", 10
        ));
        List<Map<String, Object>> previous = List.of(Map.of(
                "goodsId", 1001,
                "goodsName", "测试鞋",
                "orderSales", 40,
                "orderNumbers", 1,
                "goodsPv", 30,
                "goodsUv", 10
        ));

        List<Map<String, Object>> rows = GoodsStatSnapshotMapper.mergeWindows(current, previous);
        assertEquals(1, rows.size());
        Map<String, Object> row = rows.get(0);

        assertEquals("1001", row.get("sku_id"));
        assertEquals("测试鞋", row.get("title"));
        assertEquals("测试牌", row.get("brand"));
        assertEquals(100L, row.get("gmv_30d"));
        assertEquals(40L, row.get("gmv_prev_30d"));
        assertEquals(2L, row.get("orders_30d"));
        assertEquals(1L, row.get("orders_prev_30d"));
        assertEquals(50L, row.get("impressions_30d"));
        assertEquals(20L, row.get("clicks_30d"));
        assertEquals(10D, row.get("rate_per"));
        assertFalse(row.containsKey("supplier_brand"));
        assertFalse(row.containsKey("amount_unit"));
        assertFalse(row.containsKey("source"));
        assertFalse(row.containsKey("snapshot_hint"));

        Set<String> forbidden = Set.of(
                "goodsFirstPic",
                "goodsLink",
                "goodsId",
                "goodsName",
                "orderSales",
                "goodsPv",
                "goodsUv",
                "ratePer",
                "product_id",
                "supBrandName",
                "goodsBrandId"
        );
        for (String key : forbidden) {
            assertFalse(row.containsKey(key), "unexpected field: " + key);
        }
        assertTrue(row.containsKey("on_sale"));
    }

    @Test
    void mergeWindowsShortensLongTitle() {
        String longName = "【爆款单品】Jeep吉普户外防风防泼水男女三合一外套抓绒两件套冲锋衣超长尾巴";
        List<Map<String, Object>> current = List.of(Map.of(
                "goodsId", 2002,
                "goodsName", longName,
                "orderSales", 10.4,
                "orderNumbers", 1.0,
                "ratePer", 2.226
        ));
        Map<String, Object> row = GoodsStatSnapshotMapper.mergeWindows(current, List.of()).get(0);
        String title = String.valueOf(row.get("title"));
        assertTrue(title.length() <= GoodsStatSnapshotMapper.TITLE_MAX);
        assertTrue(title.endsWith("…"));
        assertEquals(10L, row.get("gmv_30d"));
        assertEquals(2.23D, row.get("rate_per"));
    }
}
