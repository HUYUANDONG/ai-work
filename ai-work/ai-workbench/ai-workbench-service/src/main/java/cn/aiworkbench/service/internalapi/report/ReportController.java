package cn.aiworkbench.service.internalapi.report;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 报告回写与会话报告读取。
 */
@Tag(name = "Internal Reports")
@RestController
@RequestMapping("/internal")
@RequiredArgsConstructor
public class ReportController {

    private final InMemoryReportStore reportStore;

    /**
     * 爆品报告覆盖写入。
     *
     * @param taskId 任务 ID
     * @param body   header + items
     */
    @Operation(summary = "写入爆品报告")
    @PutMapping("/tasks/{taskId}/explosion-report")
    public ResponseEntity<Void> upsertExplosion(
            @PathVariable String taskId,
            @RequestBody Map<String, Object> body) {
        reportStore.upsert(taskId, "EXPLOSION", body);
        return ResponseEntity.ok().build();
    }

    /**
     * 质检报告覆盖写入。
     *
     * @param taskId 任务 ID
     * @param body   header + items
     */
    @Operation(summary = "写入质检报告")
    @PutMapping("/tasks/{taskId}/quality-report")
    public ResponseEntity<Void> upsertQuality(
            @PathVariable String taskId,
            @RequestBody Map<String, Object> body) {
        reportStore.upsert(taskId, "QUALITY", body);
        return ResponseEntity.ok().build();
    }

    /**
     * 会话最近报告（追问用）。
     *
     * @param conversationId 会话
     * @param userId         用户
     * @param limit          条数
     * @return 报告列表
     */
    @Operation(summary = "读取会话报告")
    @GetMapping("/conversations/{conversationId}/reports")
    public Map<String, Object> conversationReports(
            @PathVariable String conversationId,
            @RequestParam("user_id") String userId,
            @RequestParam(value = "limit", defaultValue = "3") int limit) {
        return reportStore.listByConversation(conversationId, userId, limit);
    }
}
