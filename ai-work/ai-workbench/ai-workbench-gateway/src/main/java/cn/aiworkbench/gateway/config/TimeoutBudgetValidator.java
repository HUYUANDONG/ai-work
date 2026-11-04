package cn.aiworkbench.gateway.config;

import cn.aiworkbench.common.core.config.TimeoutBudgetProperties;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.Ordered;
import org.springframework.stereotype.Component;

/**
 * Gateway 启动时校验超时预算。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class TimeoutBudgetValidator implements ApplicationRunner, Ordered {

    private final TimeoutBudgetProperties timeoutBudgetProperties;

    /**
     * 校验超时预算。
     *
     * @param args 启动参数
     */
    @Override
    public void run(ApplicationArguments args) {
        timeoutBudgetProperties.validate();
        log.info("gateway timeout budget validated default={} chat={} streamIdle={}",
                timeoutBudgetProperties.getGatewayDefault(),
                timeoutBudgetProperties.getGatewayChat(),
                timeoutBudgetProperties.getGatewayStreamIdle());
    }

    /**
     * 尽早执行。
     *
     * @return 顺序
     */
    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE;
    }
}
