package cn.aiworkbench.service.workspace.infra;

import cn.aiworkbench.service.workspace.domain.ProductDraft;
import cn.aiworkbench.service.workspace.domain.ProductDraftRepository;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Repository;

import java.util.Comparator;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 未启用 MySQL 时的进程内草稿存储。{@code WB_MYSQL_ENABLED=true} 后改走 {@link MyBatisProductDraftRepository}。
 */
@Repository
@ConditionalOnProperty(name = "wb.mysql.enabled", havingValue = "false", matchIfMissing = true)
public class InMemoryProductDraftRepository implements ProductDraftRepository {

    private final ConcurrentHashMap<String, ProductDraft> store = new ConcurrentHashMap<>();

    /**
     * {@inheritDoc}
     */
    @Override
    public Optional<ProductDraft> findById(String id) {
        return Optional.ofNullable(store.get(id));
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public List<ProductDraft> findByUserId(String userId) {
        return store.values().stream()
                .filter(item -> item.getUserId().equals(userId))
                .sorted(Comparator.comparing(ProductDraft::getUpdatedAt).reversed())
                .toList();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void save(ProductDraft draft) {
        store.put(draft.getId(), draft);
    }
}
