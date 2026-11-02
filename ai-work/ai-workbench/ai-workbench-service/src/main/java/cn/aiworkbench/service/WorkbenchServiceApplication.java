package cn.aiworkbench.service;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 工作台业务服务启动类。模块化单体，不为形式拆分微服务。
 */
@SpringBootApplication
public class WorkbenchServiceApplication {

    /**
     * 启动入口。
     *
     * @param args 启动参数
     */
    public static void main(String[] args) {
        SpringApplication.run(WorkbenchServiceApplication.class, args);
    }
}
