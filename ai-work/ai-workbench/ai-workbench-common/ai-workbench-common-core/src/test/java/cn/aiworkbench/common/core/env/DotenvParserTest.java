package cn.aiworkbench.common.core.env;

import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * dotenv 解析。
 */
class DotenvParserTest {

    @Test
    void shouldParseCommentsExportAndQuotes() {
        String content = """
                # comment
                WB_NACOS_SERVER_ADDR=127.0.0.1:8848
                export WB_DUBBO_REGISTRY=N/A
                WB_SERVICE_URI="http://127.0.0.1:8080"
                EMPTY_VALUE=
                """;
        Map<String, String> parsed = DotenvParser.parse(content);
        assertEquals("127.0.0.1:8848", parsed.get("WB_NACOS_SERVER_ADDR"));
        assertEquals("N/A", parsed.get("WB_DUBBO_REGISTRY"));
        assertEquals("http://127.0.0.1:8080", parsed.get("WB_SERVICE_URI"));
        assertEquals("", parsed.get("EMPTY_VALUE"));
    }
}
