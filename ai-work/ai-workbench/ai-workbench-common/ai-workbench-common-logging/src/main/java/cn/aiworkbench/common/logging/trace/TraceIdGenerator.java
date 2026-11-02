package cn.aiworkbench.common.logging.trace;

import cn.hutool.core.util.IdUtil;
import cn.hutool.core.util.StrUtil;

/**
 * Trace ID 生成与规范化。
 */
public final class TraceIdGenerator {

    private TraceIdGenerator() {
    }

    /**
     * 若传入值为空则生成新的 Trace ID，否则原样返回（截断过长值）。
     *
     * @param incoming 上游传入的 Trace ID，可为 null
     * @return 非空 Trace ID
     */
    public static String resolve(String incoming) {
        if (StrUtil.isBlank(incoming)) {
            return IdUtil.fastSimpleUUID();
        }
        String trimmed = incoming.trim();
        return trimmed.length() > 64 ? trimmed.substring(0, 64) : trimmed;
    }
}
