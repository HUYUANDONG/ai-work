package cn.aiworkbench.common.core.env;

import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.env.EnvironmentPostProcessor;
import org.springframework.core.Ordered;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.MapPropertySource;
import org.springframework.core.env.StandardEnvironment;

import java.io.IOException;
import java.net.URISyntaxException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 启动时自动加载 Java 工作台目录的 {@code .env}，无需在 IDEA Run Configuration 里手工填环境变量。
 * <p>
 * 查找顺序：当前工作目录、类文件所在目录，以及它们的上级；同时探测 {@code ai-workbench/.env}
 * 与 {@code ai-work/ai-workbench/.env}，避免 IDEA 工作目录落在仓库根时找不到文件。
 * 已存在的操作系统环境变量优先生效，不会被 .env 覆盖。JDBC 账号单独以更高优先级写入，
 * 避免 Windows 的 {@code USERNAME} 被误当成数据源用户。
 */
public class DotenvEnvironmentPostProcessor implements EnvironmentPostProcessor, Ordered {

    static final String PROPERTY_SOURCE_NAME = "wb-dotenv";
    static final String JDBC_PROPERTY_SOURCE_NAME = "wb-dotenv-jdbc";

    private static final Log log = LogFactory.getLog(DotenvEnvironmentPostProcessor.class);

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
            log.warn("未找到 ai-workbench/.env，user.dir=" + System.getProperty("user.dir"));
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
        log.info("已加载 .env: " + envFile.toAbsolutePath());
        Map<String, Object> filtered = new LinkedHashMap<>();
        parsed.forEach((key, value) -> {
            if (!containsEnv(environment, key)) {
                filtered.put(key, value);
            }
        });
        if (!filtered.isEmpty()) {
            MapPropertySource source = new MapPropertySource(PROPERTY_SOURCE_NAME, filtered);
            if (environment.getPropertySources().contains(StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME)) {
                environment.getPropertySources()
                        .addAfter(StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME, source);
            } else {
                environment.getPropertySources().addFirst(source);
            }
        }
        Map<String, Object> jdbc = jdbcAliases(parsed);
        if (!jdbc.isEmpty()) {
            environment.getPropertySources().addFirst(new MapPropertySource(JDBC_PROPERTY_SOURCE_NAME, jdbc));
        }
    }

    /**
     * 从工作目录和类路径向上查找 Java 工作台 .env。
     *
     * @return 文件路径，找不到返回 null
     */
    static Path findEnvFile() {
        return findEnvFile(startPaths().toArray(Path[]::new));
    }

    /**
     * 从指定起点向上查找 Java 工作台 .env。
     *
     * @param starts 起点目录
     * @return 文件路径，找不到返回 null
     */
    static Path findEnvFile(Path... starts) {
        for (Path start : starts) {
            Path found = walkUpForEnv(start);
            if (found != null) {
                return found;
            }
        }
        return null;
    }

    private static List<Path> startPaths() {
        List<Path> starts = new ArrayList<>();
        addStart(starts, Path.of(System.getProperty("user.dir", ".")));
        try {
            var codeSource = DotenvEnvironmentPostProcessor.class.getProtectionDomain().getCodeSource();
            if (codeSource != null && codeSource.getLocation() != null) {
                Path fromCode = Path.of(codeSource.getLocation().toURI());
                if (Files.isRegularFile(fromCode)) {
                    fromCode = fromCode.getParent();
                }
                addStart(starts, fromCode);
            }
        } catch (URISyntaxException ignored) {
            // 类路径不是本地文件时忽略，回退到 user.dir
        }
        return starts;
    }

    private static void addStart(List<Path> starts, Path path) {
        if (path == null) {
            return;
        }
        Path normalized = path.toAbsolutePath().normalize();
        if (!starts.contains(normalized)) {
            starts.add(normalized);
        }
    }

    private static Path walkUpForEnv(Path start) {
        if (start == null) {
            return null;
        }
        Path current = start.toAbsolutePath().normalize();
        while (current != null) {
            Path[] candidates = {
                    current.resolve(".env"),
                    current.resolve("ai-workbench").resolve(".env"),
                    current.resolve("ai-work").resolve("ai-workbench").resolve(".env")
            };
            for (Path candidate : candidates) {
                if (isWorkbenchEnv(candidate)) {
                    return candidate;
                }
            }
            current = current.getParent();
        }
        return null;
    }

    /**
     * 是否为 Java 工作台 .env。跳过 Python 目录，避免误读另一份环境文件。
     *
     * @param candidate 候选文件
     * @return true 表示可用
     */
    static boolean isWorkbenchEnv(Path candidate) {
        if (candidate == null || !Files.isRegularFile(candidate)) {
            return false;
        }
        Path parent = candidate.getParent();
        if (parent != null && parent.getFileName() != null
                && "ai-workbench-python".equals(parent.getFileName().toString())) {
            return false;
        }
        return true;
    }

    private static Map<String, Object> jdbcAliases(Map<String, String> parsed) {
        Map<String, Object> jdbc = new LinkedHashMap<>();
        alias(jdbc, parsed, "WB_MYSQL_URL", "spring.datasource.url", "wb.mysql.url");
        alias(jdbc, parsed, "WB_MYSQL_USERNAME", "spring.datasource.username",
                "spring.datasource.druid.username", "wb.mysql.username");
        alias(jdbc, parsed, "WB_MYSQL_PASSWORD", "spring.datasource.password",
                "spring.datasource.druid.password", "wb.mysql.password");
        alias(jdbc, parsed, "WB_MYSQL_ENABLED", "wb.mysql.enabled");
        return jdbc;
    }

    private static void alias(Map<String, Object> target, Map<String, String> parsed, String envKey, String... keys) {
        String value = parsed.get(envKey);
        if (value == null || value.isBlank()) {
            return;
        }
        for (String key : keys) {
            target.put(key, value);
        }
    }

    private static boolean containsEnv(ConfigurableEnvironment environment, String key) {
        Map<String, Object> sys = environment.getSystemEnvironment();
        if (sys.containsKey(key)) {
            return true;
        }
        for (String existing : sys.keySet()) {
            if (existing.equalsIgnoreCase(key)) {
                return true;
            }
        }
        return false;
    }

    /**
     * 在配置文件加载前执行。
     *
     * @return 顺序
     */
    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE + 5;
    }
}
