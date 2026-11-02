package cn.aiworkbench.service.conversation.application.impl;

import cn.aiworkbench.common.core.error.CommonErrorCode;
import cn.aiworkbench.common.core.exception.BizException;
import cn.aiworkbench.common.security.identity.IdentityContext;
import cn.aiworkbench.service.conversation.api.dto.ConversationResponse;
import cn.aiworkbench.service.conversation.api.dto.CreateConversationRequest;
import cn.aiworkbench.service.conversation.application.ConversationService;
import cn.aiworkbench.service.conversation.infra.ConversationDO;
import cn.aiworkbench.service.conversation.mapper.ConversationMapper;
import cn.hutool.core.util.StrUtil;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;

/**
 * 聊天窗口用例：新开窗、列出当前用户的窗口。
 */
@Service
@RequiredArgsConstructor
public class ConversationServiceImpl implements ConversationService {

    private final ConversationMapper conversationMapper;

    /**
     * 新开一个聊天窗。主键由数据库自增，MyBatis 写回 DO 后直接返回。
     *
     * @param request 可选标题；userId、时间不从请求里取
     * @return 新窗口
     */
    @Override
    public ConversationResponse createConversation(CreateConversationRequest request) {
        String userId = requireUserId();
        String now = Instant.now().toString();
        ConversationDO row = new ConversationDO();
        row.setUserId(userId);
        row.setTitle(resolveTitle(request));
        row.setDescription(request == null ? null : request.getDescription());
        row.setCreatedAt(now);
        row.setUpdatedAt(now);
        conversationMapper.insert(row);
        return convertToResponse(row);
    }

    /**
     * 当前用户的窗口列表，新的在前。
     *
     * @return 窗口列表
     */
    @Override
    public List<ConversationResponse> listMine() {
        ConversationDO query = new ConversationDO();
        query.setUserId(requireUserId());
        return conversationMapper.selectList(query).stream()
                .map(this::convertToResponse)
                .toList();
    }

    /**
     * 读取当前登录用户。
     *
     * @return 用户 ID
     */
    private String requireUserId() {
        String userId = IdentityContext.userId();
        if (StrUtil.isBlank(userId)) {
            throw new BizException(CommonErrorCode.UNAUTHORIZED);
        }
        return userId;
    }

    /**
     * @param request 创建请求
     * @return 标题
     */
    private String resolveTitle(CreateConversationRequest request) {
        if (request == null) {
            return "新对话";
        }
        return StrUtil.blankToDefault(request.getTitle(), "新对话");
    }

    /**
     * 表行转接口响应。
     *
     * @param row 会话表记录
     * @return 响应
     */
    private ConversationResponse convertToResponse(ConversationDO row) {
        ConversationResponse response = new ConversationResponse();
        response.setId(row.getId() == null ? null : String.valueOf(row.getId()));
        response.setTitle(row.getTitle());
        response.setDescription(row.getDescription());
        response.setCreatedAt(row.getCreatedAt());
        response.setUpdatedAt(row.getUpdatedAt());
        return response;
    }
}
