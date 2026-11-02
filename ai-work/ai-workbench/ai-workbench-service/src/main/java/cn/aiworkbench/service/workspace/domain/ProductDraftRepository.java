package cn.aiworkbench.service.workspace.domain;

import java.util.List;
import java.util.Optional;

/**
 * 商品草稿持久化。当前为内存实现，接入 MySQL 后只换实现，不改领域和用例。
 */
public interface ProductDraftRepository {

    /**
     * 按 ID 查询。
     *
     * @param id 草稿 ID
     * @return 草稿
     */
    Optional<ProductDraft> findById(String id);

    /**
     * 查询某用户的草稿，新的在前。
     *
     * @param userId 用户 ID
     * @return 草稿列表
     */
    List<ProductDraft> findByUserId(String userId);

    /**
     * 新建或覆盖保存。
     *
     * @param draft 草稿
     */
    void save(ProductDraft draft);
}
