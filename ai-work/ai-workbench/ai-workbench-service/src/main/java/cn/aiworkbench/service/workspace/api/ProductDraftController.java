package cn.aiworkbench.service.workspace.api;

import cn.aiworkbench.common.web.api.ApiResult;
import cn.aiworkbench.service.workspace.api.dto.ConfirmPublishRequest;
import cn.aiworkbench.service.workspace.api.dto.ProductDraftResponse;
import cn.aiworkbench.service.workspace.api.dto.SaveProductDraftRequest;
import cn.aiworkbench.service.workspace.application.ProductDraftService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 商品草稿 HTTP 入口。只做路由和参数校验，业务在 {@link ProductDraftService}。
 */
@Tag(name = "ProductDraft")
@RestController
@RequestMapping("/api/v1/product-drafts")
@RequiredArgsConstructor
public class ProductDraftController {

    private final ProductDraftService productDraftService;

    /**
     * 新建商品草稿。
     *
     * @param request 内容
     * @return 草稿
     */
    @Operation(summary = "新建商品草稿")
    @PostMapping
    public ApiResult<ProductDraftResponse> create(@Valid @RequestBody SaveProductDraftRequest request) {
        return ApiResult.ok(productDraftService.create(request));
    }

    /**
     * 更新商品草稿。
     *
     * @param id      草稿 ID
     * @param request 内容
     * @return 草稿
     */
    @Operation(summary = "更新商品草稿")
    @PutMapping("/{id}")
    public ApiResult<ProductDraftResponse> update(@PathVariable String id,
                                                  @Valid @RequestBody SaveProductDraftRequest request) {
        return ApiResult.ok(productDraftService.update(id, request));
    }

    /**
     * 查询商品草稿。
     *
     * @param id 草稿 ID
     * @return 草稿
     */
    @Operation(summary = "查询商品草稿")
    @GetMapping("/{id}")
    public ApiResult<ProductDraftResponse> get(@PathVariable String id) {
        return ApiResult.ok(productDraftService.get(id));
    }

    /**
     * 当前用户的商品草稿列表。
     *
     * @return 列表
     */
    @Operation(summary = "我的商品草稿")
    @GetMapping
    public ApiResult<List<ProductDraftResponse>> listMine() {
        return ApiResult.ok(productDraftService.listMine());
    }

    /**
     * 确认后创建到电商系统。
     *
     * @param id      草稿 ID
     * @param request 确认标记
     * @return 发送后的草稿
     */
    @Operation(summary = "确认上架到电商")
    @PostMapping("/{id}/confirm-publish")
    public ApiResult<ProductDraftResponse> confirmPublish(@PathVariable String id,
                                                          @Valid @RequestBody ConfirmPublishRequest request) {
        return ApiResult.ok(productDraftService.confirmPublish(id, Boolean.TRUE.equals(request.getConfirmed())));
    }
}
