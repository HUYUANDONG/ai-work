package cn.aiworkbench.gateway;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 工作台 Gateway 启动类。基于 WebFlux，不依赖 Servlet 公共模块。
 */
@SpringBootApplication
public class WorkbenchGatewayApplication {

    /**
     * 启动入口。
     *
     * @param args 启动参数
     */
    public static void main(String[] args) {
        SpringApplication.run(WorkbenchGatewayApplication.class, args);
    }
}
