package cn.aiworkbench.gateway.config;

import cn.aiworkbench.common.security.auth.AuthAdapter;
import cn.aiworkbench.common.security.auth.LocalHeaderAuthAdapter;
import cn.aiworkbench.common.security.auth.UnconfiguredAuthAdapter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;

/**
 * 按环境注册认证适配器。电商系统认证方式确认前，非 local 一律视为未登录。
 */
@Configuration
public class AuthAdapterConfiguration {

    /**
     * 本地开发适配器：读取 X-Wb-Dev-User。
     *
     * @return 适配器
     */
    @Bean
    @Profile("local")
    public AuthAdapter localAuthAdapter() {
        return new LocalHeaderAuthAdapter();
    }

    /**
     * 非 local 占位适配器。
     *
     * @return 适配器
     */
    @Bean
    @Profile("!local")
    public AuthAdapter unconfiguredAuthAdapter() {
        return new UnconfiguredAuthAdapter();
    }
}
