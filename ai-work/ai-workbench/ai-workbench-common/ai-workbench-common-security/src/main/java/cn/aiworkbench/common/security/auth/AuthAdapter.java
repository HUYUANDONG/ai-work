package cn.aiworkbench.common.security.auth;

import cn.aiworkbench.common.security.identity.AuthPrincipal;

import java.util.Optional;

/**
 * 认证适配器。工作台不自建登录系统，复用电商系统的登录态。
 * <p>
 * 电商系统认证方式确认后（E-04）在此接口下增加实现：Sa-Token、JWT、Session 等。
 * 未确认前仅提供本地开发用的请求头适配器，不得用于生产。
 */
public interface AuthAdapter {

    /**
     * 根据请求解析身份。空表示未登录。
     *
     * @param request 认证请求
     * @return 身份
     */
    Optional<AuthPrincipal> authenticate(AuthRequest request);
}
