package cn.aiworkbench.common.security.auth;

import cn.aiworkbench.common.security.identity.AuthPrincipal;
import cn.hutool.core.util.StrUtil;

import java.util.Optional;

/**
 * 本地开发认证适配：读取 {@code X-Wb-Dev-User} 作为 userId。
 * 仅在 local 配置下启用，生产环境不得使用。
 */
public class LocalHeaderAuthAdapter implements AuthAdapter {

    public static final String DEV_USER_HEADER = "x-wb-dev-user";

    /**
     * 从开发头解析身份。
     *
     * @param request 认证请求
     * @return 身份
     */
    @Override
    public Optional<AuthPrincipal> authenticate(AuthRequest request) {
        if (request == null || request.getHeaders() == null) {
            return Optional.empty();
        }
        String userId = request.getHeaders().get(DEV_USER_HEADER);
        if (StrUtil.isBlank(userId)) {
            return Optional.empty();
        }
        return Optional.of(AuthPrincipal.builder().userId(userId.trim()).build());
    }
}
