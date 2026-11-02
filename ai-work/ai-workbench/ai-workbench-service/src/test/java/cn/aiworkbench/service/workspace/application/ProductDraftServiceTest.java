package cn.aiworkbench.service.workspace.application;

import cn.aiworkbench.common.core.exception.BizException;
import cn.aiworkbench.common.security.identity.AuthPrincipal;
import cn.aiworkbench.common.security.identity.IdentityContext;
import cn.aiworkbench.service.integration.ecommerce.LocalRecordingEcommerceAdapter;
import cn.aiworkbench.service.workspace.api.dto.SaveProductDraftRequest;
import cn.aiworkbench.service.workspace.domain.ProductDraftStatus;
import cn.aiworkbench.service.workspace.domain.WorkspaceErrorCode;
import cn.aiworkbench.service.workspace.infra.InMemoryProductDraftRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

/**
 * 商品草稿确认发送用例。
 */
class ProductDraftServiceTest {

    private ProductDraftService service;

    @BeforeEach
    void setUp() {
        IdentityContext.set(AuthPrincipal.builder().userId("u1").build());
        service = new ProductDraftService(new InMemoryProductDraftRepository(), new LocalRecordingEcommerceAdapter());
    }

    @AfterEach
    void tearDown() {
        IdentityContext.clear();
    }

    @Test
    void confirmPublishShouldCreateProductOnce() {
        SaveProductDraftRequest request = new SaveProductDraftRequest();
        request.setProductNumber("PN-100");
        request.setTitle("登山包");
        String id = service.create(request).getId();

        var first = service.confirmPublish(id, true);
        var second = service.confirmPublish(id, true);

        assertEquals(ProductDraftStatus.SUCCEEDED, first.getStatus());
        assertEquals("local-PN-100", first.getTargetId());
        assertEquals(first.getTargetId(), second.getTargetId());
    }

    @Test
    void confirmPublishShouldRejectWithoutConfirmation() {
        SaveProductDraftRequest request = new SaveProductDraftRequest();
        request.setProductNumber("PN-101");
        request.setTitle("登山包");
        String id = service.create(request).getId();

        BizException ex = assertThrows(BizException.class, () -> service.confirmPublish(id, false));
        assertEquals(WorkspaceErrorCode.CONFIRM_REQUIRED, ex.getErrorCode());
        assertEquals(ProductDraftStatus.DRAFT, service.get(id).getStatus());
    }

    @Test
    void otherUserShouldNotSeeDraft() {
        SaveProductDraftRequest request = new SaveProductDraftRequest();
        request.setProductNumber("PN-102");
        request.setTitle("登山包");
        String id = service.create(request).getId();

        IdentityContext.set(AuthPrincipal.builder().userId("u2").build());
        BizException ex = assertThrows(BizException.class, () -> service.get(id));
        assertEquals(WorkspaceErrorCode.DRAFT_NOT_FOUND, ex.getErrorCode());
    }
}
