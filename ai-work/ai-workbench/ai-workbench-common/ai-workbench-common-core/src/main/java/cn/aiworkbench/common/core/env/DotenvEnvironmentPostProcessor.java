package cn.aiworkbench.common.core.env;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.env.EnvironmentPostProcessor;
import org.springframework.core.Ordered;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.MapPropertySource;
import org.springframework.core.env.StandardEnvironment;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

/**
 * 启动时自动加载仓库根目录的 {@code .env}，无需在 IDEA Run Configuration 里手工填环境变量。
 * <p>
 * 查找顺序：当前工作目录及其上级目录。已存在的操作系统环境变量优先生效，不会被 .env 覆盖。
 * 找不到文件时静默跳过。
 */
public class DotenvEnvironmentPostProcessor implements EnvironmentPostProcessor, Ordered {

    static final String PROPERTY_SOURCE_NAME = "wb-dotenv";

    /**
     * 加载 .env 并插入 Environment。
     *
     * @param environment 环境
     * @param application 应用
     */
    @Override
    public void postProcessEnvironment(ConfigurableEnvironment environment, SpringApplication application) {
        Path envFile = findEnvFile();
        if (envFile == null) {
            return;
        }
        Map<String, String> parsed;
        try {
            parsed = DotenvParser.parse(Files.readString(envFile, StandardCharsets.UTF_8));
        } catch (IOException ex) {
            throw new IllegalStateException("读取 .env 失败: " + envFile.toAbsolutePath(), ex);
        }
        if (parsed.isEmpty()) {
            return;
        }
        Map<String, Object> filtered = new HashMap<>();
        parsed.forEach((key, value) -> {
            if (!environment.getSystemEnvironment().containsKey(key)) {
                filtered.put(key, value);
            }
        });
        if (filtered.isEmpty()) {
            return;
        }
        MapPropertySource source = new MapPropertySource(PROPERTY_SOURCE_NAME, filtered);
        if (environment.getPropertySources().contains(StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME)) {
            environment.getPropertySources()
                    .addAfter(StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME, source);
        } else {
            environment.getPropertySources().addFirst(source);
        }
    }

    /**
     * 从工作目录向上查找 .env。
     *
     * @return 文件路径，找不到返回 null
     */
    static Path findEnvFile() {
        Path current = Path.of(System.getProperty("user.dir", ".")).toAbsolutePath().normalize();
        while (current != null) {
            Path candidate = current.resolve(".env");
            if (Files.isRegularFile(candidate)) {
                return candidate;
            }
            current = current.getParent();
        }
        return null;
    }

    /**
     * 在配置文件加载前执行。
     *
     * @return 顺序
     */
    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE + 10;
    }
}
