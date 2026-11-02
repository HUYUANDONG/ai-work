package cn.aiworkbench.service.integration.ecommerce;

import java.util.Optional;

/**
 * 电商系统适配器。真实 Dubbo 契约确认前，local 用内存模拟创建与按编号查询。
 */
public interface EcommerceAdapter {

    /**
     * 当前适配器是否可发起副作用调用。
     *
     * @return 可用时为 true
     */
    boolean isConfigured();

    /**
     * 创建商品。编号冲突返回 {@link CreateProductResult.Kind#DUPLICATE_NUMBER}，不要当普通失败。
     * 超时或无法判断是否执行成功时抛异常，由用例标 UNKNOWN。
     *
     * @param command 创建命令
     * @return 分类结果
     */
    CreateProductResult createProduct(CreateProductCommand command);

    /**
     * 按商品编号核对是否已存在。
     *
     * @param productNumber 商品编号
     * @return 已存在时的摘要
     */
    Optional<ProductSnapshot> findByProductNumber(String productNumber);
}
