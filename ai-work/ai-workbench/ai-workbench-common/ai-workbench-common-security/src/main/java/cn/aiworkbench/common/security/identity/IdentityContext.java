package cn.aiworkbench.common.security.identity;

/**
 * 当前请求的身份上下文。基于 ThreadLocal，仅用于 Servlet 线程模型。
 * WebFlux 环境不要使用本类，应通过 Reactor Context 传递。
 */
public final class IdentityContext {

    private static final ThreadLocal<AuthPrincipal> HOLDER = new ThreadLocal<>();

    private IdentityContext() {
    }

    /**
     * 绑定当前身份。
     *
     * @param principal 身份
     */
    public static void set(AuthPrincipal principal) {
        HOLDER.set(principal);
    }

    /**
     * 读取当前身份，未绑定则返回 null。
     *
     * @return 身份
     */
    public static AuthPrincipal get() {
        return HOLDER.get();
    }

    /**
     * 读取当前用户 ID，未登录返回 null。
     *
     * @return 用户 ID
     */
    public static String userId() {
        AuthPrincipal principal = HOLDER.get();
        return principal == null ? null : principal.getUserId();
    }

    /**
     * 清除当前身份。
     */
    public static void clear() {
        HOLDER.remove();
    }
}
