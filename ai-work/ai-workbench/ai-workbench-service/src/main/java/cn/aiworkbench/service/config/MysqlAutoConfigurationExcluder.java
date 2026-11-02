package cn.aiworkbench.service.config;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.env.EnvironmentPostProcessor;
import org.springframework.core.Ordered;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.MapPropertySource;

import java.util.Map;

/**
 * 未启用 MySQL 时排除数据源、Flyway、MyBatis-Plus 自动配置，避免空 URL 导致启动失败。
 */
public class MysqlAutoConfigurationExcluder implements EnvironmentPostProcessor, Ordered {

    private static final String[] EXCLUDES = {
            "org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration",
            "org.springframework.boot.autoconfigure.jdbc.DataSourceTransactionManagerAutoConfiguration",
            "org.springframework.boot.autoconfigure.flyway.FlywayAutoConfiguration",
            "com.alibaba.druid.spring.boot3.autoconfigure.DruidDataSourceAutoConfiguration",
            "com.baomidou.mybatisplus.autoconfigure.MybatisPlusAutoConfiguration"
    };

    /**
     * 按 {@code WB_MYSQL_ENABLED} 决定是否排除数据源相关自动配置。
     *
     * @param environment 环境
     * @param application 应用
     */
    @Override
    public void postProcessEnvironment(ConfigurableEnvironment environment, SpringApplication application) {
        boolean enabled = Boolean.parseBoolean(environment.getProperty("WB_MYSQL_ENABLED", "false"));
        if (enabled) {
            return;
        }
        environment.getPropertySources().addFirst(new MapPropertySource(
                "wb-mysql-disabled",
                Map.of("spring.autoconfigure.exclude", String.join(",", EXCLUDES))
        ));
    }

    /**
     * 在加载 .env 之后执行。
     *
     * @return 顺序
     */
    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE + 20;
    }
}
