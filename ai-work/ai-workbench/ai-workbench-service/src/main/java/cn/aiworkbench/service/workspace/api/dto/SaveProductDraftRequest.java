package cn.aiworkbench.service.workspace.api.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Getter;
import lombok.Setter;

/**
 * 保存商品草稿。
 */
@Getter
@Setter
public class SaveProductDraftRequest {

    /**
     * 商品编号。确认上架前必须填写，发送后不可再改。
     */
    @Size(max = 64)
    private String productNumber;

    /**
     * 商品标题。
     */
    @NotBlank
    @Size(max = 200)
    private String title;

    /**
     * 商品描述。
     */
    @Size(max = 2000)
    private String description;
}
