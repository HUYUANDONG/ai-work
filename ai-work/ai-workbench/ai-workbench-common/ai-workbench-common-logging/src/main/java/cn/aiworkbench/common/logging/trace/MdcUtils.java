package cn.aiworkbench.common.logging.trace;

import org.slf4j.MDC;

/**
 * MDC 读写辅助。不依赖 Web 框架。
 */
public final class MdcUtils {

    private MdcUtils() {
    }

    /**
     * 写入 Trace 相关 MDC。
     *
     * @param traceId   链路 ID
     * @param requestId 请求 ID
     * @param userId    用户 ID，可为 null
     */
    public static void put(String traceId, String requestId, String userId) {
        if (traceId != null) {
            MDC.put(TraceConstants.MDC_TRACE_ID, traceId);
        }
        if (requestId != null) {
            MDC.put(TraceConstants.MDC_REQUEST_ID, requestId);
        }
        if (userId != null) {
            MDC.put(TraceConstants.MDC_USER_ID, userId);
        }
    }

    /**
     * 清除本线程 Trace 相关 MDC。
     */
    public static void clear() {
        MDC.remove(TraceConstants.MDC_TRACE_ID);
        MDC.remove(TraceConstants.MDC_REQUEST_ID);
        MDC.remove(TraceConstants.MDC_USER_ID);
    }
}
