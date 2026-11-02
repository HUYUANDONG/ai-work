package cn.aiworkbench.common.web.config;

import cn.aiworkbench.common.core.config.WorkbenchLimitProperties;
import cn.aiworkbench.common.web.exception.GlobalExceptionHandler;
import cn.aiworkbench.common.web.filter.RequestSizeLimitFilter;
import cn.aiworkbench.common.web.filter.TraceMvcFilter;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.jackson.JacksonAutoConfiguration;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.core.Ordered;

/**
 * Servlet Web 自动配置。仅注册到 Workbench Service。
 */
@AutoConfiguration(after = JacksonAutoConfiguration.class)
public class WorkbenchWebAutoConfiguration {

    /**
     * 注册全局异常处理。
     *
     * @return 处理器
     */
    @Bean
    public GlobalExceptionHandler globalExceptionHandler() {
        return new GlobalExceptionHandler();
    }

    /**
     * 注册 Trace 过滤器。
     *
     * @return 过滤器注册
     */
    @Bean
    public FilterRegistrationBean<TraceMvcFilter> traceMvcFilter() {
        FilterRegistrationBean<TraceMvcFilter> bean = new FilterRegistrationBean<>();
        bean.setFilter(new TraceMvcFilter());
        bean.setOrder(Ordered.HIGHEST_PRECEDENCE);
        bean.addUrlPatterns("/*");
        return bean;
    }

    /**
     * 注册请求体大小限制过滤器。
     *
     * @param limitProperties 上限
     * @param objectMapper    JSON
     * @return 过滤器注册
     */
    @Bean
    public FilterRegistrationBean<RequestSizeLimitFilter> requestSizeLimitFilter(
            WorkbenchLimitProperties limitProperties, ObjectMapper objectMapper) {
        FilterRegistrationBean<RequestSizeLimitFilter> bean = new FilterRegistrationBean<>();
        bean.setFilter(new RequestSizeLimitFilter(limitProperties, objectMapper));
        bean.setOrder(Ordered.HIGHEST_PRECEDENCE + 10);
        bean.addUrlPatterns("/*");
        return bean;
    }
}
