package cn.aiworkbench.common.logging.trace;

/**
 * Trace / Request ID 常量。MDC 键与 HTTP 头名称保持一致语义。
 */
public final class TraceConstants {

    public static final String TRACE_ID_HEADER = "X-Trace-Id";
    public static final String REQUEST_ID_HEADER = "X-Request-Id";
    public static final String MDC_TRACE_ID = "traceId";
    public static final String MDC_REQUEST_ID = "requestId";
    public static final String MDC_USER_ID = "userId";

    private TraceConstants() {
    }
}
