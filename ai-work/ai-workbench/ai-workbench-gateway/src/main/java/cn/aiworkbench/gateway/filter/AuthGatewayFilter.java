package cn.aiworkbench.gateway.filter;

import cn.aiworkbench.common.core.error.CommonErrorCode;
import cn.aiworkbench.common.logging.trace.TraceConstants;
import cn.aiworkbench.common.security.auth.AuthAdapter;
import cn.aiworkbench.common.security.auth.AuthRequest;
import cn.aiworkbench.common.security.identity.AuthPrincipal;
import cn.aiworkbench.common.security.identity.IdentityHeaders;
import cn.aiworkbench.common.security.identity.IdentitySigner;
import cn.hutool.core.util.StrUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.Ordered;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Gateway 认证：调用 AuthAdapter，成功后写入带签名的可信身份头。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AuthGatewayFilter implements WebFilter, Ordered {

    private static final Set<String> SKIP_PREFIXES = Set.of(
            "/actuator/health",
            "/actuator/info",
            "/favicon.ico"
    );

    private final AuthAdapter authAdapter;

    @Value("${wb.security.internal-identity-secret:}")
    private String identitySecret;

    @Value("${wb.security.allow-unsigned-identity:false}")
    private boolean allowUnsignedIdentity;

    /**
     * 认证并写入身份头。
     *
     * @param exchange 交换对象
     * @param chain    过滤器链
     * @return 完成信号
     */
    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        if (HttpMethod.OPTIONS.equals(exchange.getRequest().getMethod())
                || shouldSkip(exchange.getRequest().getPath().value())) {
            return chain.filter(exchange);
        }

        AuthRequest authRequest = toAuthRequest(exchange.getRequest());
        return Mono.fromCallable(() -> authAdapter.authenticate(authRequest))
                .flatMap(optional -> {
                    if (optional.isEmpty()) {
                        return unauthorized(exchange);
                    }
                    AuthPrincipal principal = optional.get();
                    ServerHttpRequest mutated = writeIdentity(exchange.getRequest(), principal);
                    return chain.filter(exchange.mutate().request(mutated).build());
                });
    }

    private boolean shouldSkip(String path) {
        return SKIP_PREFIXES.stream().anyMatch(path::startsWith);
    }

    private AuthRequest toAuthRequest(ServerHttpRequest request) {
        Map<String, String> headers = new HashMap<>();
        request.getHeaders().forEach((key, values) -> {
            if (values != null && !values.isEmpty()) {
                headers.put(key.toLowerCase(Locale.ROOT), values.get(0));
            }
        });
        return AuthRequest.builder()
                .path(request.getPath().value())
                .method(request.getMethod() == null ? null : request.getMethod().name())
                .authorization(request.getHeaders().getFirst("Authorization"))
                .headers(headers)
                .build();
    }

    private ServerHttpRequest writeIdentity(ServerHttpRequest request, AuthPrincipal principal) {
        long timestamp = Instant.now().getEpochSecond();
        ServerHttpRequest.Builder builder = request.mutate()
                .header(IdentityHeaders.USER_ID, principal.getUserId())
                .header(IdentityHeaders.TIMESTAMP, String.valueOf(timestamp));
        if (StrUtil.isNotBlank(principal.getTenantId())) {
            builder.header(IdentityHeaders.TENANT_ID, principal.getTenantId());
        }
        if (StrUtil.isNotBlank(principal.getMerchantId())) {
            builder.header(IdentityHeaders.MERCHANT_ID, principal.getMerchantId());
        }
        if (StrUtil.isNotBlank(identitySecret)) {
            builder.header(IdentityHeaders.SIGNATURE, IdentitySigner.sign(principal, timestamp, identitySecret));
        } else if (!allowUnsignedIdentity) {
            log.error("内部身份密钥未配置，且不允许无签名身份，请设置 WB_INTERNAL_IDENTITY_SECRET");
            throw new IllegalStateException("WB_INTERNAL_IDENTITY_SECRET 未配置");
        } else {
            log.warn("内部身份密钥未配置，正在以无签名方式传递身份，仅可用于 local");
        }
        return builder.build();
    }

    private Mono<Void> unauthorized(ServerWebExchange exchange) {
        exchange.getResponse().setStatusCode(HttpStatus.UNAUTHORIZED);
        exchange.getResponse().getHeaders().setContentType(MediaType.APPLICATION_JSON);
        String traceId = exchange.getRequest().getHeaders().getFirst(TraceConstants.TRACE_ID_HEADER);
        String body = "{\"success\":false,\"code\":\"" + CommonErrorCode.UNAUTHORIZED.getCode()
                + "\",\"message\":\"" + CommonErrorCode.UNAUTHORIZED.getMessage()
                + "\",\"traceId\":\"" + StrUtil.nullToEmpty(traceId) + "\"}";
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        return exchange.getResponse().writeWith(Mono.just(exchange.getResponse().bufferFactory().wrap(bytes)));
    }

    /**
     * 在清除身份头之后执行。
     *
     * @return 顺序
     */
    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE + 20;
    }
}
