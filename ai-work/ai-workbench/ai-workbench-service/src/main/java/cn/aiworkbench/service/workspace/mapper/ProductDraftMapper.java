package cn.aiworkbench.service.workspace.mapper;

import cn.aiworkbench.service.workspace.infra.ProductDraftDO;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * 商品草稿 Mapper。
 * <ul>
 *   <li>单表 CRUD：继承 MyBatis-Plus {@link BaseMapper}，无需 XML</li>
 *   <li>自定义查询：{@code classpath:mapper/ProductDraftMapper.xml}</li>
 * </ul>
 */
@Mapper
public interface ProductDraftMapper extends BaseMapper<ProductDraftDO> {

    /**
     * 查询某用户的草稿，新的在前。
     *
     * @param userId 用户 ID
     * @return 草稿行
     */
    List<ProductDraftDO> selectByUserId(@Param("userId") String userId);
}
