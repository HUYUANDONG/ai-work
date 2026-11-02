package cn.aiworkbench.common.web.exception;

import cn.aiworkbench.common.core.error.CommonErrorCode;
import cn.aiworkbench.common.core.exception.BizException;
import cn.aiworkbench.common.core.exception.SystemException;
import cn.aiworkbench.common.web.api.ApiResult;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.ConstraintViolationException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.servlet.resource.NoResourceFoundException;

/**
 * Servlet 全局异常处理。Gateway 不得依赖本类。
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    /**
     * 处理业务异常。
     *
     * @param ex      异常
     * @param request 请求
     * @return 响应
     */
    @ExceptionHandler(BizException.class)
    public ResponseEntity<ApiResult<Void>> handleBiz(BizException ex, HttpServletRequest request) {
        log.warn("biz exception path={} code={} message={}", request.getRequestURI(),
                ex.getErrorCode().getCode(), ex.getMessage());
        return ResponseEntity.status(ex.getErrorCode().getHttpStatus())
                .body(ApiResult.fail(ex.getErrorCode(), ex.getMessage()));
    }

    /**
     * 处理系统异常。
     *
     * @param ex      异常
     * @param request 请求
     * @return 响应
     */
    @ExceptionHandler(SystemException.class)
    public ResponseEntity<ApiResult<Void>> handleSystem(SystemException ex, HttpServletRequest request) {
        log.error("system exception path={}", request.getRequestURI(), ex);
        return ResponseEntity.status(ex.getErrorCode().getHttpStatus())
                .body(ApiResult.fail(ex.getErrorCode(), ex.getErrorCode().getMessage()));
    }

    /**
     * 处理参数校验失败。
     *
     * @param ex 异常
     * @return 响应
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiResult<Void>> handleValid(MethodArgumentNotValidException ex) {
        FieldError fieldError = ex.getBindingResult().getFieldError();
        String message = fieldError == null ? CommonErrorCode.BAD_REQUEST.getMessage()
                : fieldError.getField() + " " + fieldError.getDefaultMessage();
        log.warn("validation failed: {}", message);
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(ApiResult.fail(CommonErrorCode.BAD_REQUEST, message));
    }

    /**
     * 处理约束校验失败。
     *
     * @param ex 异常
     * @return 响应
     */
    @ExceptionHandler(ConstraintViolationException.class)
    public ResponseEntity<ApiResult<Void>> handleConstraint(ConstraintViolationException ex) {
        String message = ex.getConstraintViolations().stream()
                .findFirst()
                .map(ConstraintViolation::getMessage)
                .orElse(CommonErrorCode.BAD_REQUEST.getMessage());
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(ApiResult.fail(CommonErrorCode.BAD_REQUEST, message));
    }

    /**
     * 处理请求体不可读。
     *
     * @return 响应
     */
    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<ApiResult<Void>> handleUnreadable() {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(ApiResult.fail(CommonErrorCode.BAD_REQUEST, "请求体无法解析"));
    }

    /**
     * 处理静态资源或路径不存在。
     *
     * @return 响应
     */
    @ExceptionHandler(NoResourceFoundException.class)
    public ResponseEntity<ApiResult<Void>> handleNotFound() {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(ApiResult.fail(CommonErrorCode.NOT_FOUND, CommonErrorCode.NOT_FOUND.getMessage()));
    }

    /**
     * 处理未分类异常。
     *
     * @param ex      异常
     * @param request 请求
     * @return 响应
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResult<Void>> handleUnknown(Exception ex, HttpServletRequest request) {
        log.error("unhandled exception path={}", request.getRequestURI(), ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ApiResult.fail(CommonErrorCode.SYSTEM_ERROR, CommonErrorCode.SYSTEM_ERROR.getMessage()));
    }
}
