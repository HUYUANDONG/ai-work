package cn.aiworkbench.common.core.config;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

/**
 * 超时预算。外层必须大于内层，启动时校验，不满足则拒绝启动。
 *
 * @see docs/requirements-v1.0.0.md 13.3
 */
@Getter
@Setter
@ConfigurationProperties(prefix = "wb.timeout")
public class TimeoutBudgetProperties {

    /**
     * Python 调用"执行正式操作"的 HTTP 超时，最外层。
     */
    private Duration pythonExecuteOperation = Duration.ofSeconds(40);

    /**
     * Java 执行正式操作的总时限，含校验、占位、调用、落库。
     */
    private Duration javaExecuteOperation = Duration.ofSeconds(30);

    /**
     * 调用电商系统（创建类、提交素材）。
     */
    private Duration ecommerceMutation = Duration.ofSeconds(20);

    /**
     * 调用电商系统（查询、天然幂等操作）。
     */
    private Duration ecommerceQuery = Duration.ofSeconds(3);

    /**
     * Gateway 普通路由超时。
     */
    private Duration gatewayDefault = Duration.ofSeconds(30);

    /**
     * Gateway 流式路由空闲超时。
     */
    private Duration gatewayStreamIdle = Duration.ofSeconds(120);

    /**
     * 领取长轮询时长。Python 侧 HTTP 超时应大于此值。
     */
    private Duration claimLongPoll = Duration.ofSeconds(20);

    /**
     * 校验外层超时大于内层。
     *
     * @throws IllegalStateException 配置不满足大小关系
     */
    public void validate() {
        List<String> errors = new ArrayList<>();
        requireGreater(errors, "wb.timeout.python-execute-operation", pythonExecuteOperation,
                "wb.timeout.java-execute-operation", javaExecuteOperation);
        requireGreater(errors, "wb.timeout.java-execute-operation", javaExecuteOperation,
                "wb.timeout.ecommerce-mutation", ecommerceMutation);
        requireGreater(errors, "wb.timeout.ecommerce-mutation", ecommerceMutation,
                "wb.timeout.ecommerce-query", ecommerceQuery);
        requireGreater(errors, "wb.timeout.gateway-default", gatewayDefault,
                "wb.timeout.ecommerce-query", ecommerceQuery);
        if (claimLongPoll == null || claimLongPoll.isNegative() || claimLongPoll.isZero()) {
            errors.add("wb.timeout.claim-long-poll 必须为正");
        }
        if (gatewayStreamIdle == null || gatewayStreamIdle.isNegative() || gatewayStreamIdle.isZero()) {
            errors.add("wb.timeout.gateway-stream-idle 必须为正");
        }
        if (!errors.isEmpty()) {
            throw new IllegalStateException("超时预算配置不合法: " + String.join("; ", errors));
        }
    }

    private static void requireGreater(List<String> errors, String outerName, Duration outer,
                                       String innerName, Duration inner) {
        if (outer == null || inner == null || outer.compareTo(inner) <= 0) {
            errors.add(outerName + "(" + outer + ") 必须大于 " + innerName + "(" + inner + ")");
        }
    }
}
