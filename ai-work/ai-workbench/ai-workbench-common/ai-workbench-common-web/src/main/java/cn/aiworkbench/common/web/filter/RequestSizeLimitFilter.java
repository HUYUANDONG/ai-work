package cn.aiworkbench.common.web.filter;

import cn.aiworkbench.common.core.config.WorkbenchLimitProperties;
import cn.aiworkbench.common.core.error.CommonErrorCode;
import cn.aiworkbench.common.web.api.ApiResult;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

/**
 * 按 Content-Length 拒绝超过上限的请求体。
 */
public class RequestSizeLimitFilter extends OncePerRequestFilter {

    private final WorkbenchLimitProperties limitProperties;
    private final ObjectMapper objectMapper;

    /**
     * 创建过滤器。
     *
     * @param limitProperties 上限配置
     * @param objectMapper    JSON 序列化
     */
    public RequestSizeLimitFilter(WorkbenchLimitProperties limitProperties, ObjectMapper objectMapper) {
        this.limitProperties = limitProperties;
        this.objectMapper = objectMapper;
    }

    /**
     * 校验 Content-Length。
     *
     * @param request     请求
     * @param response    响应
     * @param filterChain 过滤器链
     */
    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        long contentLength = request.getContentLengthLong();
        if (contentLength > limitProperties.getMaxRequestBodyBytes()) {
            response.setStatus(CommonErrorCode.PAYLOAD_TOO_LARGE.getHttpStatus());
            response.setCharacterEncoding(StandardCharsets.UTF_8.name());
            response.setContentType(MediaType.APPLICATION_JSON_VALUE);
            ApiResult<Void> body = ApiResult.fail(CommonErrorCode.PAYLOAD_TOO_LARGE,
                    CommonErrorCode.PAYLOAD_TOO_LARGE.getMessage());
            response.getWriter().write(objectMapper.writeValueAsString(body));
            return;
        }
        filterChain.doFilter(request, response);
    }
}
