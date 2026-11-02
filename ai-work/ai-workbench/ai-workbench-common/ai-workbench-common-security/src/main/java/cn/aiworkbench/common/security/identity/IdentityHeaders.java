package cn.aiworkbench.common.security.identity;

import java.util.List;

/**
 * 可信身份请求头。Gateway 在入口清除这些头，认证后再写入；Service 只信任 Gateway 写入的值。
 */
public final class IdentityHeaders {

    public static final String USER_ID = "X-Wb-User-Id";
    public static final String TENANT_ID = "X-Wb-Tenant-Id";
    public static final String MERCHANT_ID = "X-Wb-Merchant-Id";
    public static final String TIMESTAMP = "X-Wb-Identity-Ts";
    public static final String SIGNATURE = "X-Wb-Identity-Sign";

    /**
     * 必须在 Gateway 入口清除的身份相关头，防止客户端伪造。
     */
    public static final List<String> STRIP_ON_ENTRY = List.of(
            USER_ID, TENANT_ID, MERCHANT_ID, TIMESTAMP, SIGNATURE,
            USER_ID.toLowerCase(), TENANT_ID.toLowerCase(), MERCHANT_ID.toLowerCase(),
            TIMESTAMP.toLowerCase(), SIGNATURE.toLowerCase()
    );

    private IdentityHeaders() {
    }
}
