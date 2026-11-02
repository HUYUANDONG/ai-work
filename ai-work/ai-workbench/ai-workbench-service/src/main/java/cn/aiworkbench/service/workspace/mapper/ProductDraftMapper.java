package cn.aiworkbench.service.workspace.mapper;

import cn.aiworkbench.service.workspace.infra.ProductDraftDO;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;

/**
 * 商品草稿 Mapper。单表 CRUD 用 {@link BaseMapper}，按用户列表用显式 SQL。
 */
@Mapper
public interface ProductDraftMapper extends BaseMapper<ProductDraftDO> {

    /**
     * 查询某用户的草稿，新的在前。
     *
     * @param userId 用户 ID
     * @return 草稿行
     */
    @Select("""
            SELECT id, user_id, product_number, title, description, status,
                   target_id, last_error, created_at, updated_at
            FROM wb_product_draft
            WHERE user_id = #{userId}
            ORDER BY updated_at DESC
            """)
    List<ProductDraftDO> selectByUserId(@Param("userId") String userId);
}
