package cn.aiworkbench.common.core.env;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

/**
 * 在 {@code SpringApplication.run} 之前把 .env 写入 system property，
 * 保证 IDEA 直接 Run main 时 JDBC 账号已存在，且优先级高于 Windows 的 {@code USERNAME}。
 */
public final class DotenvBootstrap {

    private DotenvBootstrap() {
    }

    /**
     * 加载工作台 .env 到 system property。
     */
    public static void load() {
        Path envFile = DotenvEnvironmentPostProcessor.findEnvFile();
        if (envFile == null) {
            return;
        }
        Map<String, String> parsed;
        try {
            parsed = DotenvParser.parse(Files.readString(envFile, StandardCharsets.UTF_8));
        } catch (IOException ex) {
            throw new IllegalStateException("读取 .env 失败: " + envFile.toAbsolutePath(), ex);
        }
        parsed.forEach((key, value) -> {
            if (!hasEnv(key) && System.getProperty(key) == null) {
                System.setProperty(key, value);
            }
        });
        copy(parsed, "WB_MYSQL_URL", "spring.datasource.url");
        copy(parsed, "WB_MYSQL_USERNAME",
                "spring.datasource.username", "spring.datasource.druid.username");
        copy(parsed, "WB_MYSQL_PASSWORD",
                "spring.datasource.password", "spring.datasource.druid.password");
    }

    private static void copy(Map<String, String> parsed, String envKey, String... propertyKeys) {
        String value = parsed.get(envKey);
        if (value == null || value.isBlank()) {
            return;
        }
        for (String propertyKey : propertyKeys) {
            System.setProperty(propertyKey, value);
        }
    }

    private static boolean hasEnv(String key) {
        if (System.getenv(key) != null) {
            return true;
        }
        for (String existing : System.getenv().keySet()) {
            if (existing.equalsIgnoreCase(key)) {
                return true;
            }
        }
        return false;
    }
}
