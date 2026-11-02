package cn.aiworkbench.service.internalapi.support;

import lombok.extern.slf4j.Slf4j;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 仅作用于 internalapi 包，保证错误体符合 Python 契约而非 {@code ApiResult}。
 */
@Slf4j
@Order(Ordered.HIGHEST_PRECEDENCE)
@RestControllerAdvice(basePackages = "cn.aiworkbench.service.internalapi")
public class InternalExceptionHandler {

    /**
     * @param ex 内部 API 异常
     * @return 契约错误体
     */
    @ExceptionHandler(InternalApiException.class)
    public ResponseEntity<InternalErrorBody> handleInternal(InternalApiException ex) {
        return ResponseEntity.status(ex.getStatus())
                .body(new InternalErrorBody(ex.getCode(), ex.getMessage()));
    }

    /**
     * @param ex 参数校验失败
     * @return 400
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<InternalErrorBody> handleValid(MethodArgumentNotValidException ex) {
        String message = ex.getBindingResult().getFieldErrors().stream()
                .findFirst()
                .map(err -> err.getField() + " " + err.getDefaultMessage())
                .orElse("请求参数不合法");
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(new InternalErrorBody("BAD_REQUEST", message));
    }

    /**
     * @param ex 未分类异常
     * @return 500
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<InternalErrorBody> handleUnknown(Exception ex) {
        log.error("internal api unhandled", ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(new InternalErrorBody("SYSTEM_ERROR", "系统内部错误"));
    }
}
