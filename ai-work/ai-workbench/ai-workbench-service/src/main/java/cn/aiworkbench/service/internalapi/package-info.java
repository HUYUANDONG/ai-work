/**
 * 面向 Python Agent 的内部 HTTP API。
 * <p>
 * 契约见 ai-work 仓库 {@code docs/internal-api-contract.md}：路径与字段以该文档为准，
 * 响应体为契约原始 JSON（不包 {@code ApiResult}），调用方需带 {@code X-Workbench-Caller: python}。
 */
package cn.aiworkbench.service.internalapi;
