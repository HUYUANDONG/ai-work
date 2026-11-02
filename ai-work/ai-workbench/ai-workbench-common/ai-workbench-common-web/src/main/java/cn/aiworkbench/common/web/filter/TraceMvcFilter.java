package cn.aiworkbench.common.web.filter;

import cn.aiworkbench.common.logging.trace.MdcUtils;
import cn.aiworkbench.common.logging.trace.TraceConstants;
import cn.aiworkbench.common.logging.trace.TraceIdGenerator;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.Ordered;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * Servlet Trace ID 过滤器：从请求头读取或生成，写入 MDC 与响应头。
 */
public class TraceMvcFilter extends OncePerRequestFilter implements Ordered {

    /**
     * 写入 Trace MDC，并在请求结束后清理。
     *
     * @param request     请求
     * @param response    响应
     * @param filterChain 过滤器链
     */
    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        String traceId = TraceIdGenerator.resolve(request.getHeader(TraceConstants.TRACE_ID_HEADER));
        String requestId = TraceIdGenerator.resolve(request.getHeader(TraceConstants.REQUEST_ID_HEADER));
        MdcUtils.put(traceId, requestId, null);
        response.setHeader(TraceConstants.TRACE_ID_HEADER, traceId);
        response.setHeader(TraceConstants.REQUEST_ID_HEADER, requestId);
        try {
            filterChain.doFilter(request, response);
        } finally {
            MdcUtils.clear();
        }
    }

    /**
     * 保证早于身份过滤器执行。
     *
     * @return 顺序
     */
    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE;
    }
}
