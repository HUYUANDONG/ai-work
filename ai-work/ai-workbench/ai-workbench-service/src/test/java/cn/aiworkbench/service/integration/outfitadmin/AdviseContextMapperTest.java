package cn.aiworkbench.service.integration.outfitadmin;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

/**
 * 建议阶段字段裁剪。
 */
class AdviseContextMapperTest {

    @Test
    void slimPlatesKeepsLeanFieldsAndOrdersByUv() {
        List<Map<String, Object>> raw = List.of(
                Map.of(
                        "statField", "p1",
                        "statFieldName", "首页爆款",
                        "selfPv", 100,
                        "selfUv", 40,
                        "orderSales", 200,
                        "orderNumbers", 3
                ),
                Map.of(
                        "statField", "p2",
                        "statFieldName", "活动坑",
                        "selfPv", 300,
                        "selfUv", 90,
                        "orderSales", 500,
                        "orderNumbers", 8
                )
        );
        List<Map<String, Object>> plates = AdviseContextMapper.slimPlates(raw, 12);
        assertEquals(2, plates.size());
        assertEquals("p2", plates.get(0).get("stat_field"));
        assertEquals("活动坑", plates.get(0).get("stat_field_name"));
        assertEquals(90D, plates.get(0).get("self_uv"));
        assertFalse(plates.get(0).containsKey("selfUv"));
    }

    @Test
    void slimStoreTakesLastRow() {
        List<Map<String, Object>> raw = List.of(
                Map.of("totalSales", 1, "hpageUv", 10),
                Map.of("totalSales", 99, "orderNumbers", 5, "hpageUv", 80, "conversionRate", 2.5, "statDay", "2026-11-01")
        );
        Map<String, Object> store = AdviseContextMapper.slimStore(raw);
        assertEquals(99, store.get("total_sales"));
        assertEquals(80, store.get("hpage_uv"));
        assertEquals("2026-11-01", store.get("stat_day"));
    }
}
