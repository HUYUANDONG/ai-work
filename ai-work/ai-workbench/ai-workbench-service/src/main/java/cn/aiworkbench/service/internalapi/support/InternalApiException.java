package cn.aiworkbench.service.internalapi.support;

import lombok.Getter;
import org.springframework.http.HttpStatus;

/**
 * 内部 API 业务异常，由 {@link InternalExceptionHandler} 转成契约错误体。
 */
@Getter
public class InternalApiException extends RuntimeException {

    private final String code;
    private final HttpStatus status;

    /**
     * @param status HTTP 状态
     * @param code   契约错误码
     * @param message 说明
     */
    public InternalApiException(HttpStatus status, String code, String message) {
        super(message);
        this.status = status;
        this.code = code;
    }

    /**
     * @param message 说明
     * @return 400 BAD_REQUEST
     */
    public static InternalApiException badRequest(String message) {
        return new InternalApiException(HttpStatus.BAD_REQUEST, "BAD_REQUEST", message);
    }

    /**
     * @param message 说明
     * @return 404 NOT_FOUND
     */
    public static InternalApiException notFound(String message) {
        return new InternalApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", message);
    }

    /**
     * @param message 说明
     * @return 409 CONFLICT
     */
    public static InternalApiException conflict(String message) {
        return new InternalApiException(HttpStatus.CONFLICT, "CONFLICT", message);
    }

    /**
     * @param message 说明
     * @return 503 SNAPSHOT_UNAVAILABLE
     */
    public static InternalApiException snapshotUnavailable(String message) {
        return new InternalApiException(HttpStatus.SERVICE_UNAVAILABLE, "SNAPSHOT_UNAVAILABLE", message);
    }
}
