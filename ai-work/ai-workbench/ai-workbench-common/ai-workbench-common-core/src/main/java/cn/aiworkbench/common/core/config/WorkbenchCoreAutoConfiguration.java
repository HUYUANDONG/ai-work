package cn.aiworkbench.common.core.config;

import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

/**
 * 公共配置属性注册。
 */
@AutoConfiguration
@EnableConfigurationProperties({TimeoutBudgetProperties.class, WorkbenchLimitProperties.class})
public class WorkbenchCoreAutoConfiguration {
}
