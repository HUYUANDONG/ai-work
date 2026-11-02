package cn.aiworkbench.service.internalapi.support;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.nio.charset.StandardCharsets;
import java.util.Set;

/**
 * 校验内部调用身份头 {@code X-Workbench-Caller}（本期不做 HMAC）。
 */
@Component
public class WorkbenchCallerInterceptor implements HandlerInterceptor {

    public static final String HEADER = "X-Workbench-Caller";

    private static final Set<String> ALLOWED = Set.of("python", "java");

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler)
            throws Exception {
        String caller = request.getHeader(HEADER);
        if (caller != null && ALLOWED.contains(caller.trim().toLowerCase())) {
            return true;
        }
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.getWriter().write("{\"code\":\"UNAUTHORIZED\",\"message\":\"缺少或非法 X-Workbench-Caller\"}");
        return false;
    }
}
