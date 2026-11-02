package cn.aiworkbench.common.security.identity;

import org.junit.jupiter.api.Test;

import java.time.Instant;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 内部身份签名。
 */
class IdentitySignerTest {

    @Test
    void validSignatureShouldPass() {
        AuthPrincipal principal = AuthPrincipal.builder().userId("u-1").build();
        long ts = Instant.now().getEpochSecond();
        String secret = "test-secret";
        String signature = IdentitySigner.sign(principal, ts, secret);
        assertTrue(IdentitySigner.verify(principal, ts, signature, secret, 60));
    }

    @Test
    void tamperedUserShouldFail() {
        AuthPrincipal original = AuthPrincipal.builder().userId("u-1").build();
        AuthPrincipal tampered = AuthPrincipal.builder().userId("u-2").build();
        long ts = Instant.now().getEpochSecond();
        String secret = "test-secret";
        String signature = IdentitySigner.sign(original, ts, secret);
        assertFalse(IdentitySigner.verify(tampered, ts, signature, secret, 60));
    }
}
