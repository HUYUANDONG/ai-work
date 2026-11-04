package cn.aiworkbench.service.conversation.mapper;

import cn.aiworkbench.service.conversation.infra.AiMessageDO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * AI 会话消息。SQL 见 {@code classpath:mapper/AiMessageMapper.xml}。
 */
@Mapper
public interface AiMessageMapper {

    /**
     * 追加一条消息。
     *
     * @param row 消息
     * @return 影响行数
     */
    int insert(AiMessageDO row);

    /**
     * 取最近 N 条（旧→新）。
     *
     * @param conversationId 会话
     * @param limit          条数
     * @return 消息
     */
    List<AiMessageDO> selectRecent(
            @Param("conversationId") String conversationId,
            @Param("limit") int limit);

    /**
     * 会话全部消息（旧→新，有上限）。
     *
     * @param conversationId 会话
     * @param limit          上限
     * @return 消息
     */
    List<AiMessageDO> selectByConversationId(
            @Param("conversationId") String conversationId,
            @Param("limit") int limit);

    /**
     * 取 id 大于水位的消息（旧→新），供「摘要 + 未压缩原文」回放。
     *
     * @param conversationId 会话
     * @param afterId        摘要已覆盖到的最大消息 id（不含）
     * @param limit          上限
     * @return 消息
     */
    List<AiMessageDO> selectAfterId(
            @Param("conversationId") String conversationId,
            @Param("afterId") long afterId,
            @Param("limit") int limit);

    /**
     * 统计会话消息数。
     *
     * @param conversationId 会话
     * @return 条数
     */
    int countByConversationId(@Param("conversationId") String conversationId);

    /**
     * 删除会话下全部消息。
     *
     * @param conversationId 会话
     * @return 影响行数
     */
    int deleteByConversationId(@Param("conversationId") String conversationId);
}
