package cn.aiworkbench.service.identity;

import cn.aiworkbench.common.core.error.CommonErrorCode;
import cn.aiworkbench.common.logging.trace.MdcUtils;
import cn.aiworkbench.common.logging.trace.TraceConstants;
import cn.aiworkbench.common.security.identity.AuthPrincipal;
import cn.aiworkbench.common.security.identity.IdentityContext;
import cn.aiworkbench.common.security.identity.IdentityHeaders;
import cn.aiworkbench.common.security.identity.IdentitySigner;
import cn.aiworkbench.common.web.api.ApiResult;
import cn.hutool.core.util.StrUtil;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.Ordered;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Set;

/**
 * Service 只信任 Gateway 写入的身份头。签名密钥未配置且不允许无签名时拒绝。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class IdentityMvcFilter extends OncePerRequestFilter implements Ordered {

    private static final Set<String> SKIP_PREFIXES = Set.of(
            "/actuator",
            "/v3/api-docs",
            "/swagger-ui",
            "/favicon.ico",
            // Python Agent 内部契约：本期仅校验 X-Workbench-Caller，不走用户身份头
            "/internal"
    );

    private final ObjectMapper objectMapper;

    @Value("${wb.security.internal-identity-secret:}")
    private String identitySecret;

    @Value("${wb.security.allow-unsigned-identity:false}")
    private boolean allowUnsignedIdentity;

    @Value("${wb.security.identity-ttl-seconds:60}")
    private long identityTtlSeconds;

    /**
     * 解析并绑定身份。
     *
     * @param request     请求
     * @param response    响应
     * @param filterChain 过滤器链
     */
    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        if (shouldSkip(request.getRequestURI())) {
            filterChain.doFilter(request, response);
            return;
        }
        String userId = request.getHeader(IdentityHeaders.USER_ID);
        if (StrUtil.isBlank(userId)) {
            write(response, HttpServletResponse.SC_UNAUTHORIZED, CommonErrorCode.UNAUTHORIZED);
            return;
        }
        AuthPrincipal principal = AuthPrincipal.builder()
                .userId(userId)
                .tenantId(request.getHeader(IdentityHeaders.TENANT_ID))
                .merchantId(request.getHeader(IdentityHeaders.MERCHANT_ID))
                .build();
        String timestampHeader = request.getHeader(IdentityHeaders.TIMESTAMP);
        String signature = request.getHeader(IdentityHeaders.SIGNATURE);
        if (StrUtil.isNotBlank(identitySecret)) {
            long timestamp;
            try {
                timestamp = Long.parseLong(StrUtil.nullToEmpty(timestampHeader));
            } catch (NumberFormatException ex) {
                write(response, HttpServletResponse.SC_UNAUTHORIZED, CommonErrorCode.UNAUTHORIZED);
                return;
            }
            if (!IdentitySigner.verify(principal, timestamp, signature, identitySecret, identityTtlSeconds)) {
                write(response, HttpServletResponse.SC_UNAUTHORIZED, CommonErrorCode.UNAUTHORIZED);
                return;
            }
        } else if (!allowUnsignedIdentity) {
            log.error("内部身份密钥未配置");
            write(response, HttpServletResponse.SC_SERVICE_UNAVAILABLE, CommonErrorCode.SERVICE_UNAVAILABLE);
            return;
        }

        IdentityContext.set(principal);
        String traceId = request.getHeader(TraceConstants.TRACE_ID_HEADER);
        String requestId = request.getHeader(TraceConstants.REQUEST_ID_HEADER);
        MdcUtils.put(traceId, requestId, principal.getUserId());
        try {
            filterChain.doFilter(request, response);
        } finally {
            IdentityContext.clear();
        }
    }

    private boolean shouldSkip(String uri) {
        return SKIP_PREFIXES.stream().anyMatch(uri::startsWith);
    }

    private void write(HttpServletResponse response, int status, CommonErrorCode errorCode) throws IOException {
        response.setStatus(status);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.getWriter().write(objectMapper.writeValueAsString(ApiResult.fail(errorCode, errorCode.getMessage())));
    }

    /**
     * 在 Trace 过滤器之后执行。
     *
     * @return 顺序
     */
    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE + 20;
    }
}
