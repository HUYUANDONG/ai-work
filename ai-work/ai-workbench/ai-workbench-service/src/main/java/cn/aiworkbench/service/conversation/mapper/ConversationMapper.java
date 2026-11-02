package cn.aiworkbench.service.conversation.mapper;

import org.apache.ibatis.annotations.Mapper;
import java.util.List;
import cn.aiworkbench.service.conversation.infra.ConversationDO;

@Mapper
public interface ConversationMapper {
    int insert(ConversationDO conversationDO);

    List<ConversationDO> selectList(ConversationDO conversationDO);
}