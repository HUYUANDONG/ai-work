package cn.aiworkbench.common.core.error;

/**
 * 错误码契约。
 */
public interface ErrorCode {

    /**
     * 返回机器可读的错误码。
     *
     * @return 错误码
     */
    String getCode();

    /**
     * 返回面向调用方的说明。
     *
     * @return 错误信息
     */
    String getMessage();

    /**
     * 返回建议的 HTTP 状态码。
     *
     * @return HTTP 状态码
     */
    int getHttpStatus();
}
