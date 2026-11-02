package cn.aiworkbench.service.integration.agent;

import cn.aiworkbench.common.web.api.ApiResult;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 工作台对话入口：转发 Python，并在 need_task 时入队。
 */
@Tag(name = "Agent Chat")
@RestController
@RequestMapping("/api/v1/agent")
@RequiredArgsConstructor
public class AgentChatController {

    private final ChatBridgeService chatBridgeService;

    /**
     * 对话并按需创建爆品/质检任务。
     *
     * @param request 对话请求
     * @return Python 结构化响应
     */
    @Operation(summary = "转发对话到 Python Agent")
    @PostMapping("/chat")
    public ApiResult<AgentChatResponse> chat(@RequestBody AgentChatRequest request) {
        return ApiResult.ok(chatBridgeService.handle(request));
    }
}
