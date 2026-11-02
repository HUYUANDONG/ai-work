package cn.aiworkbench.gateway.filter;

import cn.aiworkbench.common.security.identity.IdentityHeaders;
import org.springframework.core.Ordered;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;

/**
 * 入口清除客户端提交的身份头，防止伪造。认证成功后再由 AuthGatewayFilter 写入可信头。
 */
@Component
public class StripIdentityHeadersFilter implements WebFilter, Ordered {

    /**
     * 清除身份头。
     *
     * @param exchange 交换对象
     * @param chain    过滤器链
     * @return 完成信号
     */
    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        ServerHttpRequest.Builder builder = exchange.getRequest().mutate();
        for (String header : IdentityHeaders.STRIP_ON_ENTRY) {
            builder.headers(headers -> headers.remove(header));
        }
        return chain.filter(exchange.mutate().request(builder.build()).build());
    }

    /**
     * 在 Trace 之后、认证之前执行。
     *
     * @return 顺序
     */
    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE + 10;
    }
}
