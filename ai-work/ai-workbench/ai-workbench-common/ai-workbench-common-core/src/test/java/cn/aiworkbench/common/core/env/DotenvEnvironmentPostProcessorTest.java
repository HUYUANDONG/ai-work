package cn.aiworkbench.common.core.env;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * .env 查找：工作目录在仓库根时也能定位 Java 工作台文件。
 */
class DotenvEnvironmentPostProcessorTest {

    /**
     * 从仓库根探测 {@code ai-work/ai-workbench/.env}。
     *
     * @param tempDir 临时目录
     */
    @Test
    void shouldFindNestedWorkbenchEnvFromWorkspaceRoot(@TempDir Path tempDir) throws Exception {
        Path envFile = tempDir.resolve("ai-work").resolve("ai-workbench").resolve(".env");
        Files.createDirectories(envFile.getParent());
        Files.writeString(envFile, "WB_MYSQL_USERNAME=nfturbo\n");

        assertEquals(envFile, DotenvEnvironmentPostProcessor.findEnvFile(tempDir));
    }

    /**
     * Python 目录的 .env 不能抢先命中。
     *
     * @param tempDir 临时目录
     */
    @Test
    void shouldSkipPythonEnv(@TempDir Path tempDir) throws Exception {
        Path pythonEnv = tempDir.resolve("ai-workbench-python").resolve(".env");
        Files.createDirectories(pythonEnv.getParent());
        Files.writeString(pythonEnv, "PYTHON=1\n");
        assertFalse(DotenvEnvironmentPostProcessor.isWorkbenchEnv(pythonEnv));

        Path javaEnv = tempDir.resolve("ai-workbench").resolve(".env");
        Files.createDirectories(javaEnv.getParent());
        Files.writeString(javaEnv, "WB_MYSQL_USERNAME=nfturbo\n");
        assertTrue(DotenvEnvironmentPostProcessor.isWorkbenchEnv(javaEnv));
        assertEquals(javaEnv, DotenvEnvironmentPostProcessor.findEnvFile(tempDir));
    }

    /**
     * 起点下不存在工作台 .env 时返回 null。
     *
     * @param tempDir 临时目录
     */
    @Test
    void shouldReturnNullWhenMissing(@TempDir Path tempDir) {
        assertNull(DotenvEnvironmentPostProcessor.findEnvFile(tempDir));
    }
}
