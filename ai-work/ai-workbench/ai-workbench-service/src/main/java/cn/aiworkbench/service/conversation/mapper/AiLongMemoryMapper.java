package cn.aiworkbench.service.conversation.mapper;

import cn.aiworkbench.service.conversation.infra.AiLongMemoryDO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * 跨会话长期记忆。SQL 见 {@code classpath:mapper/AiLongMemoryMapper.xml}。
 */
@Mapper
public interface AiLongMemoryMapper {

    /**
     * 某一主体下的全部记忆。
     *
     * @param scope   SYSTEM 或 USER
     * @param ownerId global 或 user_id
     * @return 行
     */
    List<AiLongMemoryDO> selectByOwner(
            @Param("scope") String scope,
            @Param("ownerId") String ownerId);

    /**
     * 按键覆盖写入。
     *
     * @param row 记忆行
     * @return 影响行数
     */
    int upsert(AiLongMemoryDO row);
}
