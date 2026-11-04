package cn.aiworkbench.service.workspace.application;

import cn.aiworkbench.common.core.exception.BizException;
import cn.aiworkbench.common.security.identity.AuthPrincipal;
import cn.aiworkbench.common.security.identity.IdentityContext;
import cn.aiworkbench.service.integration.ecommerce.LocalRecordingEcommerceAdapter;
import cn.aiworkbench.service.workspace.api.dto.SaveProductDraftRequest;
import cn.aiworkbench.service.workspace.domain.WorkspaceErrorCode;
import cn.aiworkbench.service.workspace.infra.InMemoryProductDraftRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

/**
 * 上架商品 API 已暂时砍掉，公开用例一律拒绝。
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
    void createShouldRefuseWhileFeatureCut() {
        SaveProductDraftRequest request = new SaveProductDraftRequest();
        request.setProductNumber("PN-100");
        request.setTitle("登山包");
        BizException ex = assertThrows(BizException.class, () -> service.create(request));
        assertEquals(WorkspaceErrorCode.FEATURE_TEMPORARILY_CUT, ex.getErrorCode());
    }

    @Test
    void confirmPublishShouldRefuseWhileFeatureCut() {
        BizException ex = assertThrows(BizException.class, () -> service.confirmPublish("any", true));
        assertEquals(WorkspaceErrorCode.FEATURE_TEMPORARILY_CUT, ex.getErrorCode());
    }

    @Test
    void listMineShouldRefuseWhileFeatureCut() {
        BizException ex = assertThrows(BizException.class, () -> service.listMine());
        assertEquals(WorkspaceErrorCode.FEATURE_TEMPORARILY_CUT, ex.getErrorCode());
    }
}
