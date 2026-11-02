package cn.aiworkbench.service.workspace.application;

import cn.aiworkbench.common.core.error.CommonErrorCode;
import cn.aiworkbench.common.core.exception.BizException;
import cn.aiworkbench.common.security.identity.IdentityContext;
import cn.aiworkbench.service.integration.ecommerce.CreateProductCommand;
import cn.aiworkbench.service.integration.ecommerce.CreateProductResult;
import cn.aiworkbench.service.integration.ecommerce.EcommerceAdapter;
import cn.aiworkbench.service.integration.ecommerce.ProductSnapshot;
import cn.aiworkbench.service.workspace.api.dto.ProductDraftResponse;
import cn.aiworkbench.service.workspace.api.dto.SaveProductDraftRequest;
import cn.aiworkbench.service.workspace.domain.ProductDraft;
import cn.aiworkbench.service.workspace.domain.ProductDraftRepository;
import cn.aiworkbench.service.workspace.domain.ProductDraftStatus;
import cn.aiworkbench.service.workspace.domain.WorkspaceErrorCode;
import cn.hutool.core.util.StrUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 商品草稿用例：保存、查询、确认后发送。Controller 不写这段逻辑。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ProductDraftService {

    private final ProductDraftRepository productDraftRepository;
    private final EcommerceAdapter ecommerceAdapter;

    /**
     * 新建草稿。
     *
     * @param request 内容
     * @return 草稿
     */
    public ProductDraftResponse create(SaveProductDraftRequest request) {
        ProductDraft draft = ProductDraft.create(
                requireUserId(),
                request.getProductNumber(),
                request.getTitle(),
                request.getDescription()
        );
        productDraftRepository.save(draft);
        return ProductDraftResponse.from(draft);
    }

    /**
     * 更新仍可编辑的草稿。
     *
     * @param id      草稿 ID
     * @param request 内容
     * @return 草稿
     */
    public ProductDraftResponse update(String id, SaveProductDraftRequest request) {
        ProductDraft draft = loadOwned(id);
        draft.updateContent(request.getProductNumber(), request.getTitle(), request.getDescription());
        productDraftRepository.save(draft);
        return ProductDraftResponse.from(draft);
    }

    /**
     * 查询单条草稿。
     *
     * @param id 草稿 ID
     * @return 草稿
     */
    public ProductDraftResponse get(String id) {
        return ProductDraftResponse.from(loadOwned(id));
    }

    /**
     * 当前用户的草稿列表。
     *
     * @return 列表
     */
    public List<ProductDraftResponse> listMine() {
        return productDraftRepository.findByUserId(requireUserId()).stream()
                .map(ProductDraftResponse::from)
                .toList();
    }

    /**
     * 发起人确认后发送到电商。重复确认已成功的草稿直接返回，不重复创建。
     *
     * @param id        草稿 ID
     * @param confirmed 必须为 true
     * @return 发送后的草稿
     */
    public ProductDraftResponse confirmPublish(String id, boolean confirmed) {
        if (!confirmed) {
            throw new BizException(WorkspaceErrorCode.CONFIRM_REQUIRED);
        }
        ProductDraft draft = loadOwned(id);
        if (draft.getStatus() == ProductDraftStatus.SUCCEEDED) {
            return ProductDraftResponse.from(draft);
        }
        if (draft.getStatus() == ProductDraftStatus.SENDING) {
            throw new BizException(WorkspaceErrorCode.DRAFT_NOT_SENDABLE, "正在发送到电商系统，请稍后查询");
        }
        if (draft.getStatus() == ProductDraftStatus.UNKNOWN) {
            if (reconcileIfExists(draft)) {
                return ProductDraftResponse.from(draft);
            }
        }
        if (!ecommerceAdapter.isConfigured()) {
            throw new BizException(WorkspaceErrorCode.ECOMMERCE_NOT_READY);
        }
        draft.markSending();
        productDraftRepository.save(draft);
        invokeEcommerce(draft);
        return ProductDraftResponse.from(draft);
    }

    /**
     * 按商品编号核对电商是否已有该商品。
     *
     * @param draft 草稿
     * @return 核对到则已标成功
     */
    private boolean reconcileIfExists(ProductDraft draft) {
        return ecommerceAdapter.findByProductNumber(draft.reconcileKey())
                .map(snapshot -> {
                    draft.markSucceeded(snapshot.goodsId());
                    productDraftRepository.save(draft);
                    log.info("reconciled product draftId={} productNumber={} goodsId={}",
                            draft.getId(), draft.getProductNumber(), snapshot.goodsId());
                    return true;
                })
                .orElse(false);
    }

    /**
     * 调用电商创建商品，并回写草稿状态。
     *
     * @param draft 已占位为 SENDING 的草稿
     */
    private void invokeEcommerce(ProductDraft draft) {
        CreateProductCommand command = new CreateProductCommand(
                draft.getProductNumber(),
                draft.getTitle(),
                draft.getDescription(),
                draft.getUserId(),
                draft.getId()
        );
        try {
            CreateProductResult result = ecommerceAdapter.createProduct(command);
            if (result.kind() == CreateProductResult.Kind.FAILED) {
                draft.markFailed(result.message());
            } else if (result.kind() == CreateProductResult.Kind.DUPLICATE_NUMBER) {
                ProductSnapshot snapshot = ecommerceAdapter.findByProductNumber(draft.reconcileKey()).orElse(null);
                String goodsId = snapshot != null ? snapshot.goodsId() : result.goodsId();
                draft.markSucceeded(goodsId);
            } else {
                draft.markSucceeded(result.goodsId());
            }
        } catch (BizException ex) {
            draft.markFailed(ex.getMessage());
            productDraftRepository.save(draft);
            throw ex;
        } catch (RuntimeException ex) {
            log.warn("create product outcome unknown draftId={} productNumber={}",
                    draft.getId(), draft.getProductNumber(), ex);
            draft.markUnknown(ex.getMessage());
        }
        productDraftRepository.save(draft);
    }

    /**
     * 读取并校验归属。对他人草稿返回不存在，避免泄露 ID。
     *
     * @param id 草稿 ID
     * @return 草稿
     */
    private ProductDraft loadOwned(String id) {
        ProductDraft draft = productDraftRepository.findById(id)
                .orElseThrow(() -> new BizException(WorkspaceErrorCode.DRAFT_NOT_FOUND));
        draft.assertOwnedBy(requireUserId());
        return draft;
    }

    /**
     * 读取当前登录用户。
     *
     * @return 用户 ID
     */
    private String requireUserId() {
        String userId = IdentityContext.userId();
        if (StrUtil.isBlank(userId)) {
            throw new BizException(CommonErrorCode.UNAUTHORIZED);
        }
        return userId;
    }
}
