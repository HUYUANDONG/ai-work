package cn.aiworkbench.common.security.auth;

import cn.aiworkbench.common.security.identity.AuthPrincipal;

import java.util.Optional;

/**
 * 非 local 环境的占位实现：电商系统认证方式未确认前，业务请求一律视为未登录。
 */
public class UnconfiguredAuthAdapter implements AuthAdapter {

    /**
     * 始终返回未登录。
     *
     * @param request 认证请求
     * @return empty
     */
    @Override
    public Optional<AuthPrincipal> authenticate(AuthRequest request) {
        return Optional.empty();
    }
}
