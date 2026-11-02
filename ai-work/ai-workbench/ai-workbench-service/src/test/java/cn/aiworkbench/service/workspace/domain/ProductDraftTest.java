package cn.aiworkbench.service.workspace.domain;

import cn.aiworkbench.common.core.exception.BizException;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

/**
 * 商品草稿状态约束。
 */
class ProductDraftTest {

    @Test
    void updateShouldFailAfterSucceeded() {
        ProductDraft draft = ProductDraft.create("u1", "PN-1", "标题", "描述");
        draft.markSending();
        draft.markSucceeded("g-1");

        assertThrows(BizException.class, () -> draft.updateContent("PN-1", "新标题", "新描述"));
        assertEquals(ProductDraftStatus.SUCCEEDED, draft.getStatus());
    }

    @Test
    void failedDraftCanBeEditedBackToDraft() {
        ProductDraft draft = ProductDraft.create("u1", "PN-1", "标题", "描述");
        draft.markSending();
        draft.markFailed("校验失败");
        draft.updateContent("PN-1", "改过的标题", "描述");

        assertEquals(ProductDraftStatus.DRAFT, draft.getStatus());
        assertEquals("改过的标题", draft.getTitle());
    }

    @Test
    void markSendingRequiresProductNumber() {
        ProductDraft draft = ProductDraft.create("u1", "  ", "标题", "描述");
        BizException ex = assertThrows(BizException.class, draft::markSending);
        assertEquals(WorkspaceErrorCode.PRODUCT_NUMBER_REQUIRED, ex.getErrorCode());
    }
}
