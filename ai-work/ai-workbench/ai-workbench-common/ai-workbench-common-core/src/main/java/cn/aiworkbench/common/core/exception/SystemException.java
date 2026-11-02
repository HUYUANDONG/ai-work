package cn.aiworkbench.common.core.exception;

import cn.aiworkbench.common.core.error.CommonErrorCode;
import cn.aiworkbench.common.core.error.ErrorCode;
import lombok.Getter;

/**
 * 非预期的系统异常。
 */
@Getter
public class SystemException extends RuntimeException {

    private final ErrorCode errorCode;

    /**
     * 使用默认系统错误码构造。
     *
     * @param message 说明
     */
    public SystemException(String message) {
        super(message);
        this.errorCode = CommonErrorCode.SYSTEM_ERROR;
    }

    /**
     * 使用指定错误码构造。
     *
     * @param errorCode 错误码
     * @param message   说明
     * @param cause     原因
     */
    public SystemException(ErrorCode errorCode, String message, Throwable cause) {
        super(message, cause);
        this.errorCode = errorCode;
    }
}
