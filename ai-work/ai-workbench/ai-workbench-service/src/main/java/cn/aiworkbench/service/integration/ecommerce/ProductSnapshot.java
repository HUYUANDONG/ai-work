package cn.aiworkbench.service.integration.ecommerce;

/**
 * 按商品编号从电商系统核对到的摘要。
 *
 * @param goodsId       电商商品 ID
 * @param productNumber 商品编号
 * @param title         标题
 */
public record ProductSnapshot(String goodsId, String productNumber, String title) {
}
