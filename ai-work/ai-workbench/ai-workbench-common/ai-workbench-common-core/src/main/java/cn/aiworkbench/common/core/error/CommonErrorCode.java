package cn.aiworkbench.common.core.error;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

/**
 * 跨模块通用错误码。业务模块可各自扩展枚举，但不得复用这里的 code。
 */
@Getter
@RequiredArgsConstructor
public enum CommonErrorCode implements ErrorCode {

    SUCCESS("SUCCESS", "成功", 200),
    BAD_REQUEST("BAD_REQUEST", "请求参数不合法", 400),
    UNAUTHORIZED("UNAUTHORIZED", "请先登录", 401),
    FORBIDDEN("FORBIDDEN", "无权限访问该资源", 403),
    NOT_FOUND("NOT_FOUND", "资源不存在", 404),
    CONFLICT("CONFLICT", "资源状态冲突", 409),
    PAYLOAD_TOO_LARGE("PAYLOAD_TOO_LARGE", "请求体超过大小限制", 413),
    TOO_MANY_STREAMS("TOO_MANY_STREAMS", "同时打开的流式对话数量已达上限", 429),
    TOO_MANY_TASKS("TOO_MANY_TASKS", "排队与运行中的任务数量已达上限", 429),
    SERVICE_UNAVAILABLE("SERVICE_UNAVAILABLE", "服务暂时不可用", 503),
    SYSTEM_ERROR("SYSTEM_ERROR", "系统内部错误", 500);

    private final String code;
    private final String message;
    private final int httpStatus;
}
