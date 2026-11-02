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
            "com.alibaba.druid.spring.boot3.autoconfigure.DruidDataSourceAutoConfigure",
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
        boolean enabled = Boolean.parseBoolean(firstNonBlank(
                environment.getProperty("WB_MYSQL_ENABLED"),
                environment.getProperty("wb.mysql.enabled"),
                "false"));
        if (!enabled) {
            environment.getPropertySources().addFirst(new MapPropertySource(
                    "wb-mysql-disabled",
                    Map.of("spring.autoconfigure.exclude", String.join(",", EXCLUDES))
            ));
            return;
        }
        String username = firstNonBlank(
                environment.getProperty("WB_MYSQL_USERNAME"),
                environment.getProperty("spring.datasource.username"),
                environment.getProperty("wb.mysql.username"));
        if (username == null || username.isBlank()) {
            throw new IllegalStateException(
                    "WB_MYSQL_ENABLED=true 但未读到 WB_MYSQL_USERNAME。请确认已加载 ai-workbench/.env，"
                            + "或在运行配置中设置 WB_MYSQL_USERNAME / WB_MYSQL_PASSWORD。");
        }
    }

    /**
     * 取第一个非空值。
     *
     * @param values 候选
     * @return 非空字符串，全空则 null
     */
    private static String firstNonBlank(String... values) {
        if (values == null) {
            return null;
        }
        for (String value : values) {
            if (value != null && !value.isBlank()) {
                return value;
            }
        }
        return null;
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
