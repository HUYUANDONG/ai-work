package cn.aiworkbench.service.integration.outfitadmin;

import cn.hutool.crypto.digest.DigestUtil;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ThreadLocalRandom;

/**
 * 与电商后台 H5 加签一致：
 * {@code md5("/" + path + "?" + 排序后的 key=value + "&key=" + secretKey).toUpperCase()}。
 */
public final class OutfitAdminSigner {

    public static final String APP_ID = "Admin-H5";

    private OutfitAdminSigner() {
    }

    /**
     * 生成 seed：前缀 0 + 6 位随机数字再转 Number（与前端 seedId(6) 一致）。
     *
     * @return 0～999999
     */
    public static long newSeed() {
        int digits = 0;
        ThreadLocalRandom random = ThreadLocalRandom.current();
        for (int i = 0; i < 6; i++) {
            digits = digits * 10 + random.nextInt(10);
        }
        return digits;
    }

    /**
     * 计算签名并返回需要一并提交的表单字段（含 sign）。
     *
     * @param routePath 如 outfit-admin/reportStat/goodsStatList
     * @param business  仅 string/number 参与加签的业务字段
     * @param token     登录 token
     * @param secretKey 登录 secretKey
     * @param timestamp 毫秒时间戳
     * @param seed      seed
     * @return 可 qs 序列化的表单
     */
    public static Map<String, String> sign(
            String routePath,
            Map<String, ?> business,
            String token,
            String secretKey,
            long timestamp,
            long seed) {
        Map<String, Object> source = new LinkedHashMap<>();
        source.put("appId", APP_ID);
        source.put("timestamp", timestamp);
        source.put("seed", seed);
        source.put("token", token == null ? "" : token);
        if (business != null) {
            business.forEach((key, value) -> {
                if (key != null && value != null) {
                    source.put(key, value);
                }
            });
        }
        List<String> pairs = new ArrayList<>();
        source.forEach((key, value) -> pairs.add(key + "=" + encodeValue(value)));
        pairs.sort(String::compareTo);
        String raw = "/" + routePath + "?" + String.join("&", pairs) + "&key=" + secretKey;
        Map<String, String> form = new LinkedHashMap<>();
        source.forEach((key, value) -> form.put(key, encodeValue(value)));
        form.put("sign", DigestUtil.md5Hex(raw).toUpperCase());
        return form;
    }

    /**
     * JS：字符串原样，其它 JSON.stringify（数字即十进制）。
     *
     * @param value 字段值
     * @return 加签文本
     */
    static String encodeValue(Object value) {
        if (value instanceof String text) {
            return text;
        }
        return String.valueOf(value);
    }
}
