package cn.aiworkbench.service.integration.agent;

import cn.aiworkbench.common.core.error.CommonErrorCode;
import cn.aiworkbench.common.core.exception.BizException;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

/**
 * Agent 关闭时的占位实现。
 */
@Component
@ConditionalOnProperty(prefix = "wb.agent", name = "enabled", havingValue = "false")
public class UnconfiguredAgentApiClient implements AgentApiClient {

    /**
     * {@inheritDoc}
     */
    @Override
    public AgentChatResponse chat(AgentChatRequest request) {
        throw new BizException(CommonErrorCode.SERVICE_UNAVAILABLE, "Python Agent 未启用");
    }
}
