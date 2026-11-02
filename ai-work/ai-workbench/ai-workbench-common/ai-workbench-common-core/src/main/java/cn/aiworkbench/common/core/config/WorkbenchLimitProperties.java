package cn.aiworkbench.common.core.config;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 并发与数量上限，默认值来自需求 13.1。
 */
@Getter
@Setter
@ConfigurationProperties(prefix = "wb.limit")
public class WorkbenchLimitProperties {

    /**
     * 每用户同时打开的流式对话数。
     */
    private int maxStreamsPerUser = 3;

    /**
     * 单实例流式对话总数。
     */
    private int maxStreamsPerInstance = 500;

    /**
     * 每用户排队与运行中的任务数。
     */
    private int maxActiveTasksPerUser = 20;

    /**
     * 单实例同时调用电商系统的并发数。
     */
    private int maxEcommerceConcurrency = 50;

    /**
     * 请求体大小上限，字节。
     */
    private long maxRequestBodyBytes = 1024L * 1024L;

    /**
     * 回调载荷大小上限，字节。
     */
    private long maxCallbackPayloadBytes = 256L * 1024L;
}
