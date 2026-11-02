package cn.aiworkbench.service.workspace.domain;

import cn.aiworkbench.common.core.exception.BizException;
import cn.hutool.core.util.IdUtil;
import cn.hutool.core.util.StrUtil;
import lombok.Getter;

import java.time.Instant;

/**
 * 商品草稿聚合。工作台只存草稿和发送状态，商品权威数据在电商系统。
 */
@Getter
public class ProductDraft {

    private final String id;
    private final String userId;
    private String productNumber;
    private String title;
    private String description;
    private ProductDraftStatus status;
    private String targetId;
    private String lastError;
    private final Instant createdAt;
    private Instant updatedAt;

    private ProductDraft(String id, String userId, String productNumber, String title, String description,
                         ProductDraftStatus status, String targetId, String lastError,
                         Instant createdAt, Instant updatedAt) {
        this.id = id;
        this.userId = userId;
        this.productNumber = productNumber;
        this.title = title;
        this.description = description;
        this.status = status;
        this.targetId = targetId;
        this.lastError = lastError;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
    }

    /**
     * 从持久化记录恢复聚合，不走新建校验。
     *
     * @param id            草稿 ID
     * @param userId        归属用户
     * @param productNumber 商品编号
     * @param title         标题
     * @param description   描述
     * @param status        状态
     * @param targetId      电商商品 ID
     * @param lastError     最近错误
     * @param createdAt     创建时间
     * @param updatedAt     更新时间
     * @return 草稿
     */
    public static ProductDraft restore(String id, String userId, String productNumber, String title, String description,
                                       ProductDraftStatus status, String targetId, String lastError,
                                       Instant createdAt, Instant updatedAt) {
        return new ProductDraft(id, userId, productNumber, title, description, status, targetId, lastError,
                createdAt, updatedAt);
    }

    /**
     * 新建草稿。
     *
     * @param userId         归属用户
     * @param productNumber  商品编号，可空，确认发送前必须有值
     * @param title          标题
     * @param description    描述
     * @return 草稿
     */
    public static ProductDraft create(String userId, String productNumber, String title, String description) {
        Instant now = Instant.now();
        return new ProductDraft(
                IdUtil.fastSimpleUUID(),
                userId,
                StrUtil.trim(productNumber),
                title,
                description,
                ProductDraftStatus.DRAFT,
                null,
                null,
                now,
                now
        );
    }

    /**
     * 校验草稿属于当前用户。
     *
     * @param currentUserId 当前用户
     */
    public void assertOwnedBy(String currentUserId) {
        if (!userId.equals(currentUserId)) {
            throw new BizException(WorkspaceErrorCode.DRAFT_NOT_FOUND);
        }
    }

    /**
     * 更新可编辑字段。失败状态改内容后回到 DRAFT。
     *
     * @param productNumber 商品编号
     * @param title         标题
     * @param description   描述
     */
    public void updateContent(String productNumber, String title, String description) {
        if (!status.editable()) {
            throw new BizException(WorkspaceErrorCode.DRAFT_NOT_EDITABLE);
        }
        this.productNumber = StrUtil.trim(productNumber);
        this.title = title;
        this.description = description;
        this.status = ProductDraftStatus.DRAFT;
        this.lastError = null;
        touch();
    }

    /**
     * 确认发送占位。插入成功即为不可回头点，取消不能撤回这次调用。
     */
    public void markSending() {
        if (!status.sendable()) {
            throw new BizException(WorkspaceErrorCode.DRAFT_NOT_SENDABLE);
        }
        if (StrUtil.isBlank(productNumber)) {
            throw new BizException(WorkspaceErrorCode.PRODUCT_NUMBER_REQUIRED);
        }
        this.status = ProductDraftStatus.SENDING;
        this.lastError = null;
        touch();
    }

    /**
     * 电商创建成功或按编号核对到已存在。
     *
     * @param goodsId 电商侧商品 ID
     */
    public void markSucceeded(String goodsId) {
        this.status = ProductDraftStatus.SUCCEEDED;
        this.targetId = goodsId;
        this.lastError = null;
        touch();
    }

    /**
     * 电商明确失败，允许改稿后再次确认。
     *
     * @param error 原因
     */
    public void markFailed(String error) {
        this.status = ProductDraftStatus.FAILED;
        this.lastError = error;
        touch();
    }

    /**
     * 结果不确定，再次确认时先按商品编号核对。
     *
     * @param error 原因
     */
    public void markUnknown(String error) {
        this.status = ProductDraftStatus.UNKNOWN;
        this.lastError = error;
        touch();
    }

    /**
     * 首次发送前锁定的核对键，重试不得更换。
     *
     * @return 商品编号
     */
    public String reconcileKey() {
        return productNumber;
    }

    private void touch() {
        this.updatedAt = Instant.now();
    }
}
