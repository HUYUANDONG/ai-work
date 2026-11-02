package cn.aiworkbench.gateway.filter;

import cn.aiworkbench.common.logging.trace.MdcUtils;
import cn.aiworkbench.common.logging.trace.TraceConstants;
import cn.aiworkbench.common.logging.trace.TraceIdGenerator;
import org.springframework.core.Ordered;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;
import reactor.util.context.Context;

/**
 * Gateway Trace ID：生成或透传，写入请求头、响应头和 Reactor Context。
 * WebFlux 下 MDC 不会自动跟随线程，因此在每个信号上回填 MDC。
 */
@Component
public class TraceWebFilter implements WebFilter, Ordered {

    /**
     * 处理 Trace。
     *
     * @param exchange 交换对象
     * @param chain    过滤器链
     * @return 完成信号
     */
    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        String incoming = exchange.getRequest().getHeaders().getFirst(TraceConstants.TRACE_ID_HEADER);
        String traceId = TraceIdGenerator.resolve(incoming);
        String requestId = TraceIdGenerator.resolve(
                exchange.getRequest().getHeaders().getFirst(TraceConstants.REQUEST_ID_HEADER));

        ServerHttpRequest mutatedRequest = exchange.getRequest().mutate()
                .header(TraceConstants.TRACE_ID_HEADER, traceId)
                .header(TraceConstants.REQUEST_ID_HEADER, requestId)
                .build();
        exchange.getResponse().getHeaders().set(TraceConstants.TRACE_ID_HEADER, traceId);
        ServerWebExchange mutated = exchange.mutate().request(mutatedRequest).build();

        return chain.filter(mutated)
                .contextWrite(Context.of(TraceConstants.MDC_TRACE_ID, traceId,
                        TraceConstants.MDC_REQUEST_ID, requestId))
                .doOnEach(signal -> MdcUtils.put(traceId, requestId, null))
                .doFinally(signalType -> MdcUtils.clear());
    }

    /**
     * 最先执行，保证后续过滤器能读到 Trace 头。
     *
     * @return 顺序
     */
    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE;
    }
}
