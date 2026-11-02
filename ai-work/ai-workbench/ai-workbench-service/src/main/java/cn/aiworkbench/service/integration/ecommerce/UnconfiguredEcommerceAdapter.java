package cn.aiworkbench.service.integration.ecommerce;

import cn.aiworkbench.common.core.error.CommonErrorCode;
import cn.aiworkbench.common.core.exception.BizException;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.stereotype.Component;

import java.util.Optional;

/**
 * 非 local 且尚未接入真实 Dubbo 时的占位，拒绝任何副作用调用。
 */
@Component
@ConditionalOnMissingBean(EcommerceAdapter.class)
public class UnconfiguredEcommerceAdapter implements EcommerceAdapter {

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean isConfigured() {
        return false;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public CreateProductResult createProduct(CreateProductCommand command) {
        throw new BizException(CommonErrorCode.SERVICE_UNAVAILABLE, "电商系统尚未接入，无法真正创建商品");
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public Optional<ProductSnapshot> findByProductNumber(String productNumber) {
        return Optional.empty();
    }
}
