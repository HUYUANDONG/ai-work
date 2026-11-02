package cn.aiworkbench.common.security.auth;

import lombok.Builder;
import lombok.Getter;

import java.util.Collections;
import java.util.Map;

/**
 * 框架无关的认证请求，由 Gateway / Service 各自从 HTTP 请求适配而来。
 */
@Getter
@Builder
public class AuthRequest {

    private final String path;
    private final String method;
    /**
     * 原始 Authorization 或 Token 头，适配器内使用后不得写入日志。
     */
    private final String authorization;
    /**
     * 其余请求头，键已转为小写。
     */
    @Builder.Default
    private final Map<String, String> headers = Collections.emptyMap();
}
