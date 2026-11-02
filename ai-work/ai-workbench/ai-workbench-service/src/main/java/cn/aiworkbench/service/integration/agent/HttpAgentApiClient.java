package cn.aiworkbench.service.integration.agent;

import cn.aiworkbench.common.core.error.CommonErrorCode;
import cn.aiworkbench.common.core.exception.BizException;
import cn.aiworkbench.service.internalapi.support.WorkbenchCallerInterceptor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;

import java.net.http.HttpClient;
import java.time.Duration;

/**
 * 真实 HTTP 调用 Python {@code /internal/chat}。
 */
@Slf4j
@Component
@ConditionalOnProperty(prefix = "wb.agent", name = "enabled", havingValue = "true", matchIfMissing = true)
public class HttpAgentApiClient implements AgentApiClient {

    private final RestClient restClient;

    /**
     * @param restClientBuilder Boot 提供的 Builder（带统一 ObjectMapper）
     * @param baseUrl           Python Agent Base URL
     * @param timeoutSeconds    超时秒
     */
    public HttpAgentApiClient(
            RestClient.Builder restClientBuilder,
            @Value("${wb.agent.python-base-url:http://127.0.0.1:8001}") String baseUrl,
            @Value("${wb.agent.timeout-seconds:40}") long timeoutSeconds) {
        String normalized = baseUrl.replaceAll("/$", "");
        log.info("Python Agent baseUrl={}", normalized);
        HttpClient httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(5))
                .build();
        JdkClientHttpRequestFactory factory = new JdkClientHttpRequestFactory(httpClient);
        factory.setReadTimeout(Duration.ofSeconds(timeoutSeconds));
        this.restClient = restClientBuilder
                .baseUrl(normalized)
                .requestFactory(factory)
                .defaultHeader(WorkbenchCallerInterceptor.HEADER, "java")
                .build();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public AgentChatResponse chat(AgentChatRequest request) {
        try {
            AgentChatResponse response = restClient.post()
                    .uri("/internal/chat")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(request)
                    .retrieve()
                    .body(AgentChatResponse.class);
            if (response == null) {
                throw new BizException(CommonErrorCode.SERVICE_UNAVAILABLE, "Python Agent 返回空响应");
            }
            return response;
        } catch (RestClientResponseException ex) {
            log.error("call python /internal/chat failed status={} body={}",
                    ex.getStatusCode(), ex.getResponseBodyAsString(), ex);
            throw new BizException(CommonErrorCode.SERVICE_UNAVAILABLE,
                    "Python Agent 不可用: HTTP " + ex.getStatusCode().value(), ex);
        } catch (RestClientException ex) {
            log.error("call python /internal/chat failed", ex);
            throw new BizException(CommonErrorCode.SERVICE_UNAVAILABLE,
                    "Python Agent 不可用: " + ex.getMessage(), ex);
        }
    }
}
