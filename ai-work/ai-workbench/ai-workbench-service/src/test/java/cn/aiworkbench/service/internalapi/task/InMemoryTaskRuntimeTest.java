package cn.aiworkbench.service.internalapi.task;

import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 入队后等待 complete 能拿到摘要。
 */
class InMemoryTaskRuntimeTest {

    @Test
    void awaitFinishedReturnsSummary() throws InterruptedException {
        InMemoryTaskRuntime runtime = new InMemoryTaskRuntime();
        Map<String, Object> created = runtime.enqueue(Map.of("task_type", "EXPLOSION"));
        String taskId = String.valueOf(created.get("task_id"));
        String lease = String.valueOf(created.get("lease_token"));
        Thread worker = new Thread(() -> {
            runtime.claim(List.of("EXPLOSION"), "v", "w");
            runtime.complete(taskId, lease, Map.of("summary", "分析完成：SKU-001"));
        });
        worker.start();
        Optional<Map<String, Object>> done = runtime.awaitFinished(taskId, Duration.ofSeconds(2));
        worker.join(2000);
        assertTrue(done.isPresent());
        assertEquals("COMPLETED", done.get().get("status"));
        @SuppressWarnings("unchecked")
        Map<String, Object> body = (Map<String, Object>) done.get().get("complete_body");
        assertEquals("分析完成：SKU-001", body.get("summary"));
    }
}
