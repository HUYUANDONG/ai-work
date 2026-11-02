package cn.aiworkbench.common.logging.mask;

import ch.qos.logback.classic.pattern.ClassicConverter;
import ch.qos.logback.classic.spi.ILoggingEvent;

/**
 * Logback 转换器：输出脱敏后的日志消息。
 */
public class MaskingConverter extends ClassicConverter {

    /**
     * 将事件消息脱敏后输出。
     *
     * @param event 日志事件
     * @return 脱敏消息
     */
    @Override
    public String convert(ILoggingEvent event) {
        return SensitiveMasker.mask(event.getFormattedMessage());
    }
}
