package cn.aiworkbench.common.logging.mask;

import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 日志敏感字段脱敏。不记录密码、Token、API Key；手机号部分遮盖。
 */
public final class SensitiveMasker {

    private static final Set<String> SENSITIVE_KEYS = Set.of(
            "password", "passwd", "pwd", "secret", "token", "accesstoken", "refreshtoken",
            "authorization", "satoken", "apikey", "api_key", "accesskey", "accesskeysecret",
            "privatekey", "credential"
    );

    private static final Pattern JSON_FIELD = Pattern.compile(
            "(?i)(\"(?:password|passwd|pwd|secret|token|accessToken|refreshToken|authorization|satoken|apiKey|api_key|accessKey|accessKeySecret|privateKey|credential)\"\\s*:\\s*\")([^\"]*)(\")"
    );

    private static final Pattern KEY_VALUE = Pattern.compile(
            "(?i)((?:password|passwd|pwd|secret|token|authorization|satoken|api[_-]?key|access[_-]?key)\\s*[=:]\\s*)([^,\\s]+)"
    );

    private static final Pattern MOBILE = Pattern.compile("(?<!\\d)(1[3-9]\\d)(\\d{4})(\\d{4})(?!\\d)");

    private SensitiveMasker() {
    }

    /**
     * 对日志原文做脱敏。
     *
     * @param raw 原始日志
     * @return 脱敏后文本；入参为 null 时返回 null
     */
    public static String mask(String raw) {
        if (raw == null || raw.isEmpty()) {
            return raw;
        }
        String masked = JSON_FIELD.matcher(raw).replaceAll("$1***$3");
        masked = KEY_VALUE.matcher(masked).replaceAll("$1***");
        Matcher mobileMatcher = MOBILE.matcher(masked);
        StringBuffer buffer = new StringBuffer();
        while (mobileMatcher.find()) {
            mobileMatcher.appendReplacement(buffer, mobileMatcher.group(1) + "****" + mobileMatcher.group(3));
        }
        mobileMatcher.appendTail(buffer);
        return buffer.toString();
    }

    /**
     * 判断字段名是否敏感。
     *
     * @param fieldName 字段名
     * @return 是否敏感
     */
    public static boolean isSensitiveKey(String fieldName) {
        if (fieldName == null) {
            return false;
        }
        String normalized = fieldName.replace("-", "").replace("_", "").toLowerCase(Locale.ROOT);
        return SENSITIVE_KEYS.contains(normalized);
    }
}
