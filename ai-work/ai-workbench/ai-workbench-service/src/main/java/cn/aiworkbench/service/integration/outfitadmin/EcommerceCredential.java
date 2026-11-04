package cn.aiworkbench.service.integration.outfitadmin;

/**
 * 电商后台登录凭证（token + secretKey），用于 reportStat 加签。
 *
 * @param userId    工作台用户
 * @param token     Cookie token
 * @param secretKey Cookie secretKey
 */
public record EcommerceCredential(String userId, String token, String secretKey) {
}
