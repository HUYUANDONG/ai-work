package cn.aiworkbench.service.integration.ecommerce;

/**
 * 向电商系统创建商品的命令。字段独立于工作台草稿实体，后续对接真实 Dubbo DTO 时只改适配器内部映射。
 *
 * @param productNumber  商品编号，核对键
 * @param title          标题
 * @param description    描述
 * @param operatorUserId 发起人
 * @param draftId        工作台草稿 ID，仅用于追踪
 */
public record CreateProductCommand(
        String productNumber,
        String title,
        String description,
        String operatorUserId,
        String draftId
) {
}
