package cn.aiworkbench.service.workspace.infra;

import cn.aiworkbench.service.workspace.domain.ProductDraft;
import cn.aiworkbench.service.workspace.domain.ProductDraftRepository;
import cn.aiworkbench.service.workspace.mapper.ProductDraftMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * 基于 {@link ProductDraftMapper} 的草稿仓储。
 */
@Repository
@ConditionalOnProperty(name = "wb.mysql.enabled", havingValue = "true")
@RequiredArgsConstructor
public class MyBatisProductDraftRepository implements ProductDraftRepository {

    private final ProductDraftMapper productDraftMapper;

    /**
     * {@inheritDoc}
     */
    @Override
    public Optional<ProductDraft> findById(String id) {
        ProductDraftDO row = productDraftMapper.selectById(id);
        return Optional.ofNullable(row).map(ProductDraftConverter::toDomain);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public List<ProductDraft> findByUserId(String userId) {
        return productDraftMapper.selectByUserId(userId).stream()
                .map(ProductDraftConverter::toDomain)
                .toList();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void save(ProductDraft draft) {
        ProductDraftDO row = ProductDraftConverter.toDO(draft);
        if (productDraftMapper.selectById(draft.getId()) == null) {
            productDraftMapper.insert(row);
            return;
        }
        productDraftMapper.updateById(row);
    }
}
