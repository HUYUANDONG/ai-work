package cn.aiworkbench.service.observability;

import cn.aiworkbench.common.security.identity.IdentityContext;
import cn.aiworkbench.common.web.api.ApiResult;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 系统探活接口，用于验证 Gateway 转发、Trace ID 贯通和身份传递。不含业务逻辑。
 */
@Tag(name = "System")
@RestController
@RequestMapping("/api/v1/system")
public class SystemPingController {

    /**
     * 返回服务状态与当前身份摘要。
     *
     * @return 探活结果
     */
    @Operation(summary = "服务探活")
    @GetMapping("/ping")
    public ApiResult<Map<String, Object>> ping() {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("service", "ai-workbench-service");
        body.put("status", "UP");
        body.put("timestamp", Instant.now().toString());
        body.put("userId", IdentityContext.userId());
        return ApiResult.ok(body);
    }
}
