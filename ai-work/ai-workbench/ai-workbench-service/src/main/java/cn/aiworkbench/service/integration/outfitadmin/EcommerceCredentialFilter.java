package cn.aiworkbench.service.integration.outfitadmin;

import cn.aiworkbench.common.security.identity.IdentityContext;
import cn.hutool.core.util.StrUtil;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.core.Ordered;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * 从前端对话请求里收下电商 token / secretKey，供后续 Worker 拉销量。
 */
@Component
@RequiredArgsConstructor
public class EcommerceCredentialFilter extends OncePerRequestFilter implements Ordered {

    public static final String TOKEN_HEADER = "X-Wb-Admin-Token";
    public static final String SECRET_HEADER = "X-Wb-Admin-Secret";

    private final EcommerceCredentialStore store;

    /**
     * 捕获凭证。
     *
     * @param request     请求
     * @param response    响应
     * @param filterChain 链
     */
    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain) throws ServletException, IOException {
        String token = request.getHeader(TOKEN_HEADER);
        String secret = request.getHeader(SECRET_HEADER);
        String userId = IdentityContext.userId();
        if (StrUtil.isBlank(userId)) {
            userId = request.getHeader("X-Wb-User-Id");
        }
        store.put(userId, token, secret);
        filterChain.doFilter(request, response);
    }

    /**
     * 在身份过滤器之后执行。
     *
     * @return 顺序
     */
    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE + 30;
    }
}
