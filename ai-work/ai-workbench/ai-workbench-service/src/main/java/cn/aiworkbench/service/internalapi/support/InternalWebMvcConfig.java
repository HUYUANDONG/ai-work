package cn.aiworkbench.service.internalapi.support;

import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * 注册内部 API 调用方拦截器。
 */
@Configuration
@RequiredArgsConstructor
public class InternalWebMvcConfig implements WebMvcConfigurer {

    private final WorkbenchCallerInterceptor workbenchCallerInterceptor;

    /**
     * {@inheritDoc}
     */
    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(workbenchCallerInterceptor)
                .addPathPatterns("/internal/**");
    }
}
