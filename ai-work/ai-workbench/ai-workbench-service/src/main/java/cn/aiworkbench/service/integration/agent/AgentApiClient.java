package cn.aiworkbench.service.integration.agent;

/**
 * Python Agent API 客户端。
 * <p>
 * 契约见 ai-work 仓库 {@code docs/internal-api-contract.md} §2.1。
 */
public interface AgentApiClient {

    /**
     * 调用 Python 对话入口。
     *
     * @param request 对话请求
     * @return 意图与可选 need_task
     */
    AgentChatResponse chat(AgentChatRequest request);
}
