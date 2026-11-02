package cn.aiworkbench.common.logging.mask;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 敏感字段脱敏。
 */
class SensitiveMaskerTest {

    @Test
    void shouldMaskJsonPasswordAndToken() {
        String raw = "{\"password\":\"NFTurbo666\",\"token\":\"abc-def\"}";
        String masked = SensitiveMasker.mask(raw);
        assertTrue(masked.contains("***"));
        assertFalse(masked.contains("NFTurbo666"));
        assertFalse(masked.contains("abc-def"));
    }

    @Test
    void shouldMaskMobile() {
        String masked = SensitiveMasker.mask("联系手机 13812345678");
        assertEquals("联系手机 138****5678", masked);
    }
}
