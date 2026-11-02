package cn.aiworkbench.common.core.env;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 解析 dotenv 格式。支持空行、# 注释、可选 export 前缀、引号包裹的值。
 */
public final class DotenvParser {

    private DotenvParser() {
    }

    /**
     * 解析文件内容。
     *
     * @param content 文件文本
     * @return 键值对，保持出现顺序
     */
    public static Map<String, String> parse(String content) {
        Map<String, String> result = new LinkedHashMap<>();
        if (content == null || content.isEmpty()) {
            return result;
        }
        String[] lines = content.split("\\r?\\n");
        for (String rawLine : lines) {
            String line = rawLine.trim();
            if (line.isEmpty() || line.startsWith("#")) {
                continue;
            }
            if (line.regionMatches(true, 0, "export ", 0, 7)) {
                line = line.substring(7).trim();
            }
            int index = line.indexOf('=');
            if (index <= 0) {
                continue;
            }
            String key = line.substring(0, index).trim();
            if (key.isEmpty() || !key.chars().allMatch(ch -> Character.isLetterOrDigit(ch) || ch == '_')) {
                continue;
            }
            String value = unquote(line.substring(index + 1).trim());
            result.put(key, value);
        }
        return result;
    }

    private static String unquote(String value) {
        if (value.length() >= 2) {
            char first = value.charAt(0);
            char last = value.charAt(value.length() - 1);
            if ((first == '"' && last == '"') || (first == '\'' && last == '\'')) {
                return value.substring(1, value.length() - 1);
            }
        }
        return value;
    }
}
