package cn.aiworkbench.common.security.identity;

import lombok.Builder;
import lombok.Getter;

/**
 * 认证后的身份。tenantId、merchantId 在电商系统身份模型确认前可为空。
 */
@Getter
@Builder
public class AuthPrincipal {

    private final String userId;
    private final String tenantId;
    private final String merchantId;
}
