package cn.aiworkbench.service.integration.ecommerce;

import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * local 环境模拟电商：按商品编号唯一，重复创建返回 DUPLICATE_NUMBER。
 */
@Slf4j
@Profile("local")
@Component
public class LocalRecordingEcommerceAdapter implements EcommerceAdapter {

    private final ConcurrentHashMap<String, ProductSnapshot> products = new ConcurrentHashMap<>();

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean isConfigured() {
        return true;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public CreateProductResult createProduct(CreateProductCommand command) {
        ProductSnapshot existing = products.get(command.productNumber());
        if (existing != null) {
            log.info("local ecommerce duplicate productNumber={} goodsId={}",
                    command.productNumber(), existing.goodsId());
            return CreateProductResult.duplicateNumber(existing.goodsId(), command.productNumber());
        }
        String goodsId = "local-" + command.productNumber();
        ProductSnapshot created = new ProductSnapshot(goodsId, command.productNumber(), command.title());
        products.put(command.productNumber(), created);
        log.info("local ecommerce created productNumber={} goodsId={} draftId={}",
                command.productNumber(), goodsId, command.draftId());
        return CreateProductResult.succeeded(goodsId, command.productNumber());
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public Optional<ProductSnapshot> findByProductNumber(String productNumber) {
        return Optional.ofNullable(products.get(productNumber));
    }
}
