package cn.aiworkbench.service.workspace.api.dto;

import cn.aiworkbench.service.workspace.domain.ProductDraft;
import cn.aiworkbench.service.workspace.domain.ProductDraftStatus;
import lombok.Builder;
import lombok.Getter;

import java.time.Instant;

/**
 * 商品草稿对外视图。
 */
@Getter
@Builder
public class ProductDraftResponse {

    private String id;
    private String productNumber;
    private String title;
    private String description;
    private ProductDraftStatus status;
    private String targetId;
    private String lastError;
    private Instant createdAt;
    private Instant updatedAt;

    /**
     * 从领域对象转换。
     *
     * @param draft 草稿
     * @return 响应
     */
    public static ProductDraftResponse from(ProductDraft draft) {
        return ProductDraftResponse.builder()
                .id(draft.getId())
                .productNumber(draft.getProductNumber())
                .title(draft.getTitle())
                .description(draft.getDescription())
                .status(draft.getStatus())
                .targetId(draft.getTargetId())
                .lastError(draft.getLastError())
                .createdAt(draft.getCreatedAt())
                .updatedAt(draft.getUpdatedAt())
                .build();
    }
}
