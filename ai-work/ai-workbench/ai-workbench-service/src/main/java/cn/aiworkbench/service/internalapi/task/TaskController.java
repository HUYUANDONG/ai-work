package cn.aiworkbench.service.internalapi.task;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * 任务领取与生命周期内部 API。
 */
@Tag(name = "Internal Tasks")
@RestController
@RequestMapping("/internal/tasks")
@RequiredArgsConstructor
public class TaskController {

    private final InMemoryTaskRuntime taskRuntime;

    /**
     * 联调/对话建任务：入队供 Worker claim。
     *
     * @param body 任务草稿
     * @return 入队结果
     */
    @Operation(summary = "入队任务（对话 need_task / 联调）")
    @PostMapping("/enqueue")
    public Map<String, Object> enqueue(@RequestBody Map<String, Object> body) {
        return taskRuntime.enqueue(body == null ? Map.of() : body);
    }

    /**
     * 领取任务；无任务返回 204。
     *
     * @param body claim 请求
     * @return 任务或空
     */
    @Operation(summary = "领取任务")
    @PostMapping("/claim")
    public ResponseEntity<Map<String, Object>> claim(@RequestBody Map<String, Object> body) {
        Map<String, Object> req = body == null ? Map.of() : body;
        @SuppressWarnings("unchecked")
        List<String> types = req.get("task_types") instanceof List<?> list
                ? list.stream().map(String::valueOf).toList()
                : List.of();
        String workflowVersion = String.valueOf(req.getOrDefault("workflow_version", "explosion-quality-1.0.0"));
        String workerId = String.valueOf(req.getOrDefault("worker_id", "py-worker"));
        return taskRuntime.claim(types, workflowVersion, workerId)
                .<ResponseEntity<Map<String, Object>>>map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.status(HttpStatus.NO_CONTENT).build());
    }

    /**
     * 思考过程事件。
     *
     * @param taskId 任务 ID
     * @param body   lease_token + event
     */
    @Operation(summary = "上报进度/思考事件")
    @PostMapping("/{taskId}/progress")
    public ResponseEntity<Void> progress(
            @PathVariable String taskId,
            @RequestBody Map<String, Object> body) {
        Map<String, Object> req = body == null ? Map.of() : body;
        String leaseToken = String.valueOf(req.get("lease_token"));
        @SuppressWarnings("unchecked")
        Map<String, Object> event = req.get("event") instanceof Map<?, ?> m
                ? (Map<String, Object>) m
                : Map.of();
        taskRuntime.postProgress(taskId, leaseToken, event);
        return ResponseEntity.ok().build();
    }

    /**
     * 心跳。
     *
     * @param taskId 任务 ID
     * @param body   lease_token / progress
     * @return 控制位
     */
    @Operation(summary = "任务心跳")
    @PostMapping("/{taskId}/heartbeat")
    public Map<String, Object> heartbeat(
            @PathVariable String taskId,
            @RequestBody Map<String, Object> body) {
        Map<String, Object> req = body == null ? Map.of() : body;
        return taskRuntime.heartbeat(
                taskId,
                String.valueOf(req.get("lease_token")),
                String.valueOf(req.getOrDefault("progress", "")));
    }

    /**
     * 完成。
     *
     * @param taskId 任务 ID
     * @param body   完成载荷
     */
    @Operation(summary = "任务完成")
    @PostMapping("/{taskId}/complete")
    public ResponseEntity<Void> complete(
            @PathVariable String taskId,
            @RequestBody Map<String, Object> body) {
        Map<String, Object> req = body == null ? Map.of() : body;
        taskRuntime.complete(taskId, String.valueOf(req.get("lease_token")), req);
        return ResponseEntity.ok().build();
    }

    /**
     * 失败。
     *
     * @param taskId 任务 ID
     * @param body   失败载荷
     */
    @Operation(summary = "任务失败")
    @PostMapping("/{taskId}/fail")
    public ResponseEntity<Void> fail(
            @PathVariable String taskId,
            @RequestBody Map<String, Object> body) {
        Map<String, Object> req = body == null ? Map.of() : body;
        taskRuntime.fail(taskId, String.valueOf(req.get("lease_token")), req);
        return ResponseEntity.ok().build();
    }
}
