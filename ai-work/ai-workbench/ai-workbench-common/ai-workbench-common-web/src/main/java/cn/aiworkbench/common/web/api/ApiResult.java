package cn.aiworkbench.common.web.api;

import cn.aiworkbench.common.core.error.CommonErrorCode;
import cn.aiworkbench.common.core.error.ErrorCode;
import cn.aiworkbench.common.logging.trace.TraceConstants;
import lombok.Getter;
import lombok.Setter;
import org.slf4j.MDC;

/**
 * Servlet 层统一响应。
 *
 * @param <T> 数据类型
 */
@Getter
@Setter
public class ApiResult<T> {

    private boolean success;
    private String code;
    private String message;
    private T data;
    private String traceId;

    /**
     * 成功响应。
     *
     * @param data 数据
     * @param <T>  数据类型
     * @return 响应
     */
    public static <T> ApiResult<T> ok(T data) {
        ApiResult<T> result = new ApiResult<>();
        result.setSuccess(true);
        result.setCode(CommonErrorCode.SUCCESS.getCode());
        result.setMessage(CommonErrorCode.SUCCESS.getMessage());
        result.setData(data);
        result.setTraceId(MDC.get(TraceConstants.MDC_TRACE_ID));
        return result;
    }

    /**
     * 失败响应。
     *
     * @param errorCode 错误码
     * @param message   说明
     * @param <T>       数据类型
     * @return 响应
     */
    public static <T> ApiResult<T> fail(ErrorCode errorCode, String message) {
        ApiResult<T> result = new ApiResult<>();
        result.setSuccess(false);
        result.setCode(errorCode.getCode());
        result.setMessage(message == null ? errorCode.getMessage() : message);
        result.setTraceId(MDC.get(TraceConstants.MDC_TRACE_ID));
        return result;
    }
}
