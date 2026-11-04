package cn.aiworkbench.service.integration.outfitadmin;

import cn.hutool.core.util.StrUtil;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 按 userId 记住最近一次从前端带上来的电商 token。
 * Worker 拉特征时已不在用户 HTTP 线程里，只能查这里。
 */
@Component
public class EcommerceCredentialStore {

    private final ConcurrentHashMap<String, EcommerceCredential> byUser = new ConcurrentHashMap<>();

    @Value("${wb.admin.token:}")
    private String envToken;

    @Value("${wb.admin.secret-key:}")
    private String envSecret;

    /**
     * 保存或覆盖某用户的电商凭证。
     *
     * @param userId    用户
     * @param token     token
     * @param secretKey secretKey
     */
    public void put(String userId, String token, String secretKey) {
        if (StrUtil.isBlank(userId) || StrUtil.isBlank(token) || StrUtil.isBlank(secretKey)) {
            return;
        }
        byUser.put(userId, new EcommerceCredential(userId, token, secretKey));
    }

    /**
     * 查找用户凭证；没有则尝试环境变量兜底（本机联调用）。
     *
     * @param userId 用户
     * @return 凭证
     */
    public Optional<EcommerceCredential> find(String userId) {
        if (StrUtil.isNotBlank(userId)) {
            EcommerceCredential stored = byUser.get(userId);
            if (stored != null) {
                return Optional.of(stored);
            }
        }
        if (StrUtil.isNotBlank(envToken) && StrUtil.isNotBlank(envSecret)) {
            return Optional.of(new EcommerceCredential(
                    StrUtil.blankToDefault(userId, "env"), envToken, envSecret));
        }
        return Optional.empty();
    }
}
