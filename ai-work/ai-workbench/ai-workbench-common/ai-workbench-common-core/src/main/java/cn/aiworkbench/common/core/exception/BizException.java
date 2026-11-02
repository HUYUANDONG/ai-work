package cn.aiworkbench.common.core.exception;

import cn.aiworkbench.common.core.error.ErrorCode;
import lombok.Getter;

/**
 * 可预期的业务异常，由全局异常处理器转换为统一响应。
 */
@Getter
public class BizException extends RuntimeException {

    private final ErrorCode errorCode;

    /**
     * 使用错误码的默认文案构造。
     *
     * @param errorCode 错误码
     */
    public BizException(ErrorCode errorCode) {
        super(errorCode.getMessage());
        this.errorCode = errorCode;
    }

    /**
     * 使用自定义文案构造。
     *
     * @param errorCode 错误码
     * @param message   覆盖默认文案
     */
    public BizException(ErrorCode errorCode, String message) {
        super(message);
        this.errorCode = errorCode;
    }

    /**
     * 使用自定义文案和原因构造。
     *
     * @param errorCode 错误码
     * @param message   覆盖默认文案
     * @param cause     原因
     */
    public BizException(ErrorCode errorCode, String message, Throwable cause) {
        super(message, cause);
        this.errorCode = errorCode;
    }
}
