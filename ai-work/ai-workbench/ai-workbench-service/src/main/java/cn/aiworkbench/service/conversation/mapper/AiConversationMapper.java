package cn.aiworkbench.service.conversation.mapper;

import cn.aiworkbench.service.conversation.infra.AiConversationDO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * AI 会话表（含 LTM 槽位 JSON）。SQL 见 {@code classpath:mapper/AiConversationMapper.xml}。
 */
@Mapper
public interface AiConversationMapper {

    /**
     * 按对外会话 ID 查询。
     *
     * @param conversationId 会话 ID
     * @return 行或 null
     */
    AiConversationDO selectByConversationId(@Param("conversationId") String conversationId);

    /**
     * 新建会话（已存在则忽略）。
     *
     * @param row 行
     * @return 影响行数
     */
    int insertIgnore(AiConversationDO row);

    /**
     * 更新 LTM 槽位并刷新 updated_at。
     *
     * @param conversationId   会话 ID
     * @param sessionStateJson JSON
     * @return 影响行数
     */
    int updateSessionState(
            @Param("conversationId") String conversationId,
            @Param("sessionStateJson") String sessionStateJson);

    /**
     * 仅刷新 updated_at（有新消息时）。
     *
     * @param conversationId 会话 ID
     * @return 影响行数
     */
    int touch(@Param("conversationId") String conversationId);

    /**
     * 当前用户会话列表（新→旧）。
     *
     * @param userId 用户
     * @return 会话行
     */
    List<AiConversationDO> selectByUserId(@Param("userId") String userId);

    /**
     * 更新标题。
     *
     * @param conversationId 会话
     * @param title          标题
     * @return 影响行数
     */
    int updateTitle(
            @Param("conversationId") String conversationId,
            @Param("title") String title);

    /**
     * 删除会话行。
     *
     * @param conversationId 会话
     * @param userId         用户（防越权）
     * @return 影响行数
     */
    int deleteByConversationId(
            @Param("conversationId") String conversationId,
            @Param("userId") String userId);
}
