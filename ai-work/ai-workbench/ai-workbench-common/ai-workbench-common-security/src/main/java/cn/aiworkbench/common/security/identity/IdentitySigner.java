package cn.aiworkbench.common.security.identity;

import cn.hutool.core.util.StrUtil;
import cn.hutool.crypto.digest.HMac;
import cn.hutool.crypto.digest.HmacAlgorithm;

import java.nio.charset.StandardCharsets;
import java.time.Instant;

/**
 * 内部身份头 HMAC 签名，防止客户端直连 Service 时伪造身份。
 */
public final class IdentitySigner {

    private IdentitySigner() {
    }

    /**
     * 计算签名。
     *
     * @param principal 身份
     * @param timestamp 秒级时间戳
     * @param secret    内部密钥
     * @return 十六进制签名
     */
    public static String sign(AuthPrincipal principal, long timestamp, String secret) {
        String payload = payload(principal, timestamp);
        HMac hmac = new HMac(HmacAlgorithm.HmacSHA256, secret.getBytes(StandardCharsets.UTF_8));
        return hmac.digestHex(payload);
    }

    /**
     * 校验签名与时间窗口。
     *
     * @param principal     身份
     * @param timestamp     秒级时间戳
     * @param signature     签名
     * @param secret        内部密钥
     * @param ttlSeconds    允许的时间偏差，秒
     * @return 是否通过
     */
    public static boolean verify(AuthPrincipal principal, long timestamp, String signature,
                                 String secret, long ttlSeconds) {
        if (principal == null || StrUtil.hasBlank(principal.getUserId(), signature, secret)) {
            return false;
        }
        long now = Instant.now().getEpochSecond();
        if (Math.abs(now - timestamp) > ttlSeconds) {
            return false;
        }
        String expected = sign(principal, timestamp, secret);
        return constantTimeEquals(expected, signature);
    }

    private static String payload(AuthPrincipal principal, long timestamp) {
        return StrUtil.nullToEmpty(principal.getUserId()) + "|"
                + StrUtil.nullToEmpty(principal.getTenantId()) + "|"
                + StrUtil.nullToEmpty(principal.getMerchantId()) + "|"
                + timestamp;
    }

    private static boolean constantTimeEquals(String left, String right) {
        if (left == null || right == null || left.length() != right.length()) {
            return false;
        }
        int result = 0;
        for (int i = 0; i < left.length(); i++) {
            result |= left.charAt(i) ^ right.charAt(i);
        }
        return result == 0;
    }
}
