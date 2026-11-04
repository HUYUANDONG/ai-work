package cn.aiworkbench.service.workspace.api;

import cn.aiworkbench.common.core.error.CommonErrorCode;
import cn.aiworkbench.common.core.exception.BizException;
import cn.aiworkbench.common.web.api.ApiResult;
import cn.aiworkbench.service.internalapi.task.InMemoryTaskRuntime;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 前端任务控制：暂停 / 取消 / 继续。
 */
@Tag(name = "Task Control")
@RestController
@RequestMapping("/api/v1/tasks")
@RequiredArgsConstructor
public class TaskControlController {

    private final InMemoryTaskRuntime taskRuntime;

    /**
     * 控制进行中或已暂停的任务。
     *
     * @param taskId 任务 ID
     * @param body   action=pause|cancel|resume，可选 reason
     * @return 结果
     */
    @Operation(summary = "暂停 / 取消 / 继续任务")
    @PostMapping("/{taskId}/control")
    public ApiResult<Map<String, Object>> control(
            @PathVariable String taskId,
            @RequestBody(required = false) Map<String, Object> body) {
        Map<String, Object> req = body == null ? Map.of() : body;
        String action = String.valueOf(req.getOrDefault("action", "")).trim().toLowerCase();
        String reason = String.valueOf(req.getOrDefault("reason", ""));
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("task_id", taskId);
        switch (action) {
            case "pause" -> {
                taskRuntime.requestPause(taskId, reason.isBlank() ? "用户暂停" : reason);
                result.put("action", "pause");
                result.put("ok", true);
            }
            case "cancel" -> {
                taskRuntime.requestCancel(taskId, reason.isBlank() ? "用户取消" : reason);
                result.put("action", "cancel");
                result.put("ok", true);
            }
            case "resume", "continue" -> {
                Map<String, Object> created = taskRuntime.resumePaused(taskId);
                result.put("action", "resume");
                result.put("ok", true);
                result.put("task_id", String.valueOf(created.get("task_id")));
                result.put("resumed_from", taskId);
            }
            default -> throw new BizException(CommonErrorCode.BAD_REQUEST, "action 须为 pause|cancel|resume");
        }
        return ApiResult.ok(result);
    }
}
