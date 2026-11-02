package cn.aiworkbench.service.integration.ecommerce;

/**
 * 创建商品的分类结果。超时等不确定情况不要用本对象表达，由适配器抛出异常让用例标 UNKNOWN。
 */
public record CreateProductResult(Kind kind, String goodsId, String productNumber, String message) {

    /**
     * 结果分类。
     */
    public enum Kind {
        /** 新建成功。 */
        SUCCEEDED,
        /** 编号已存在，调用方应按编号核对而不是当业务失败。 */
        DUPLICATE_NUMBER,
        /** 电商明确拒绝。 */
        FAILED
    }

    /**
     * 新建成功。
     *
     * @param goodsId       电商商品 ID
     * @param productNumber 商品编号
     * @return 结果
     */
    public static CreateProductResult succeeded(String goodsId, String productNumber) {
        return new CreateProductResult(Kind.SUCCEEDED, goodsId, productNumber, null);
    }

    /**
     * 编号重复。
     *
     * @param goodsId       已存在商品 ID，未知时可为 null
     * @param productNumber 商品编号
     * @return 结果
     */
    public static CreateProductResult duplicateNumber(String goodsId, String productNumber) {
        return new CreateProductResult(Kind.DUPLICATE_NUMBER, goodsId, productNumber, "商品编号已存在");
    }

    /**
     * 明确失败。
     *
     * @param message 原因
     * @return 结果
     */
    public static CreateProductResult failed(String message) {
        return new CreateProductResult(Kind.FAILED, null, null, message);
    }
}
