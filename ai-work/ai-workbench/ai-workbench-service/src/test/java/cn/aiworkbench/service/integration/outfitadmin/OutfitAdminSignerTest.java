package cn.aiworkbench.service.integration.outfitadmin;

import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * 加签必须与前端 src/utils/sign.js 一致。
 */
class OutfitAdminSignerTest {

    @Test
    void signMatchesSortedQueryAndMd5() {
        Map<String, Object> business = new LinkedHashMap<>();
        business.put("pageNum", 1);
        business.put("pageSize", 50);
        business.put("startTime", "2026-01-01 00:00:00");
        business.put("endTime", "2026-01-07 00:00:00");
        Map<String, String> form = OutfitAdminSigner.sign(
                OutfitAdminReportClient.GOODS_STAT_PATH,
                business,
                "tok",
                "secret",
                1700000000000L,
                123456L);
        assertEquals("Admin-H5", form.get("appId"));
        assertEquals("1", form.get("pageNum"));
        // python hashlib.md5 of the same concatenated string
        assertEquals("37055DB033EA669F5D5E491DE41C4357", form.get("sign"));
    }
}
