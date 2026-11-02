package cn.aiworkbench.service.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * OpenAPI 文档配置。仅 Service 暴露，Gateway 不暴露文档入口。
 */
@Configuration
public class OpenApiConfiguration {

    /**
     * 注册 OpenAPI 描述。
     *
     * @return OpenAPI
     */
    @Bean
    public OpenAPI workbenchOpenApi() {
        return new OpenAPI().info(new Info()
                .title("AI 商家运营工作台 API")
                .version("1.0.0")
                .description("Workbench Service HTTP 接口。阶段一仅包含系统探活，业务接口按后续阶段接入。"));
    }
}
