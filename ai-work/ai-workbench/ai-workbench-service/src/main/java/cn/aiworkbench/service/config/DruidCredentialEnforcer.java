package cn.aiworkbench.service.config;

import com.alibaba.druid.pool.DruidDataSource;
import org.springframework.beans.factory.config.BeanPostProcessor;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.EnvironmentAware;
import org.springframework.core.Ordered;
import org.springframework.core.PriorityOrdered;
import org.springframework.core.env.Environment;
import org.springframework.lang.NonNull;
import org.springframework.stereotype.Component;

/**
 * Windows 下操作系统 {@code USERNAME} 会被 Druid 绑成数据库用户。
 * 在 {@code init()} 连库前强制改回 {@code WB_MYSQL_USERNAME}/{@code WB_MYSQL_PASSWORD}。
 * <p>
 * {@link BeanPostProcessor} 创建早于常规构造器注入，因此用 {@link EnvironmentAware} 拿环境。
 */
@Component
@ConditionalOnClass(DruidDataSource.class)
@ConditionalOnProperty(name = "wb.mysql.enabled", havingValue = "true")
public class DruidCredentialEnforcer implements BeanPostProcessor, PriorityOrdered, EnvironmentAware {

    private Environment environment;

    /**
     * BeanPostProcessor 需要无参构造。
     */
    public DruidCredentialEnforcer() {
    }

    /**
     * 注入启动环境。
     *
     * @param environment 环境
     */
    @Override
    public void setEnvironment(@NonNull Environment environment) {
        this.environment = environment;
    }

    /**
     * 覆盖 Druid 已绑定的错误账号。
     *
     * @param bean     Bean
     * @param beanName 名称
     * @return 原 Bean
     */
    @Override
    public Object postProcessBeforeInitialization(@NonNull Object bean, @NonNull String beanName) {
        if (bean instanceof DruidDataSource dataSource) {
            String username = firstNonBlank(
                    getProperty("WB_MYSQL_USERNAME"),
                    getProperty("spring.datasource.username"),
                    getProperty("wb.mysql.username"));
            String password = firstNonBlank(
                    getProperty("WB_MYSQL_PASSWORD"),
                    getProperty("spring.datasource.password"),
                    getProperty("wb.mysql.password"));
            if (username == null || username.isBlank()) {
                throw new IllegalStateException(
                        "WB_MYSQL_ENABLED=true 但未读到 WB_MYSQL_USERNAME。请确认已加载 ai-workbench/.env。");
            }
            String osUser = System.getProperty("user.name", "");
            if (!osUser.isBlank() && osUser.equals(username) && (password == null || password.isBlank())) {
                throw new IllegalStateException(
                        "数据源用户 '" + username + "' 来自 Windows 登录名且没有密码。"
                                + "请使用 .env 中的 WB_MYSQL_USERNAME / WB_MYSQL_PASSWORD（nfturbo）。");
            }
            dataSource.setUsername(username);
            dataSource.setPassword(password == null ? "" : password);
        }
        return bean;
    }

    /**
     * 早于 Druid {@code init()} 执行。
     *
     * @return 顺序
     */
    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE;
    }

    private String getProperty(String key) {
        if (environment != null) {
            String value = environment.getProperty(key);
            if (value != null && !value.isBlank()) {
                return value;
            }
        }
        return System.getProperty(key);
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
}
