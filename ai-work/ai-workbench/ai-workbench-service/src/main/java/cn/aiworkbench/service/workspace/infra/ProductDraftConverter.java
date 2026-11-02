package cn.aiworkbench.service.workspace.infra;

import cn.aiworkbench.service.workspace.domain.ProductDraft;
import cn.aiworkbench.service.workspace.domain.ProductDraftStatus;

/**
 * 草稿领域对象与表行互转。
 */
public final class ProductDraftConverter {

    private static final int LAST_ERROR_MAX = 500;

    private ProductDraftConverter() {
    }

    /**
     * 领域对象转表行。
     *
     * @param draft 草稿
     * @return 表行
     */
    public static ProductDraftDO toDO(ProductDraft draft) {
        ProductDraftDO row = new ProductDraftDO();
        row.setId(draft.getId());
        row.setUserId(draft.getUserId());
        row.setProductNumber(draft.getProductNumber());
        row.setTitle(draft.getTitle());
        row.setDescription(draft.getDescription());
        row.setStatus(draft.getStatus().name());
        row.setTargetId(draft.getTargetId());
        row.setLastError(truncate(draft.getLastError()));
        row.setCreatedAt(draft.getCreatedAt());
        row.setUpdatedAt(draft.getUpdatedAt());
        return row;
    }

    /**
     * 表行转领域对象。
     *
     * @param row 表行
     * @return 草稿
     */
    public static ProductDraft toDomain(ProductDraftDO row) {
        return ProductDraft.restore(
                row.getId(),
                row.getUserId(),
                row.getProductNumber(),
                row.getTitle(),
                row.getDescription(),
                ProductDraftStatus.valueOf(row.getStatus()),
                row.getTargetId(),
                row.getLastError(),
                row.getCreatedAt(),
                row.getUpdatedAt()
        );
    }

    /**
     * 截断错误信息以适配表字段长度。
     *
     * @param value 原文
     * @return 截断后的值
     */
    private static String truncate(String value) {
        if (value == null || value.length() <= LAST_ERROR_MAX) {
            return value;
        }
        return value.substring(0, LAST_ERROR_MAX);
    }
}
