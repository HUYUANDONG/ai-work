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
 * 爆品 / 质检报告的 HTTP 入口。Python 筛完爆品后 {@code PUT} 报告；追问时 {@code GET} 最近几份。
 *
 * <p>本类注解一览（都不是本仓库自己写的）：
 * <ul>
 *   <li>{@code @Tag} — 第三方 springdoc/OpenAPI，不是 Spring 核心。Swagger 文档里的分组名。</li>
 *   <li>{@code @RestController} — Spring Web。声明「这是接口类」：方法返回值直接写成 JSON
 *       （等于 {@code @Controller} + {@code @ResponseBody}）。</li>
 *   <li>{@code @RequestMapping} — Spring Web。本类所有路径的公共前缀 {@code /internal}。</li>
 *   <li>{@code @RequiredArgsConstructor} — Lombok（第三方代码生成，不是 Spring）。
 *       给下面 {@code final} 字段生成构造器；Spring 启动时走这个构造器把 {@link InMemoryReportStore} 注入进来。
 *       所以你看不到 {@code new InMemoryReportStore()}。</li>
 * </ul>
 */
@Tag(name = "Internal Reports")
@RestController
@RequestMapping("/internal")
@RequiredArgsConstructor
public class ReportController {

    /** Spring 按类型注入：全项目只有一个 {@link InMemoryReportStore} Bean。 */
    private final InMemoryReportStore reportStore;

    /**
     * 覆盖写入一份爆品报告（同一 {@code taskId} 再写会替换）。
     *
     * @param taskId 任务 ID，来自 URL 路径 {@code /tasks/{taskId}/...}
     * @param body   JSON：{@code header} + {@code items}
     * @return 空 body 的 200
     */
    @Operation(summary = "写入爆品报告") // 第三方 OpenAPI：只影响文档标题，不影响运行
    @PutMapping("/tasks/{taskId}/explosion-report") // Spring：HTTP PUT，幂等覆盖
    public ResponseEntity<Void> upsertExplosion(
            @PathVariable String taskId, // Spring：把 URL 里的 {taskId} 填进参数
            @RequestBody Map<String, Object> body) { // Spring：把 JSON 请求体反序列化成 Map
        reportStore.upsert(taskId, "EXPLOSION", body);
        return ResponseEntity.ok().build();
    }

    /**
     * 覆盖写入一份质检报告。
     *
     * @param taskId 任务 ID
     * @param body   JSON：{@code header} + {@code items}
     * @return 空 body 的 200
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
     * 读某会话最近若干份报告，给追问拼上下文。
     *
     * @param conversationId 会话 ID（路径变量）
     * @param userId         归属用户（查询参数，必填）
     * @param limit          条数，缺省 3
     * @return {@code conversation_id} + {@code reports}
     */
    @Operation(summary = "读取会话报告")
    @GetMapping("/conversations/{conversationId}/reports") // Spring：HTTP GET，只读
    public Map<String, Object> conversationReports(
            @PathVariable String conversationId,
            @RequestParam("user_id") String userId, // Spring：?user_id= 必填；JSON 蛇形，Java 驼峰
            @RequestParam(value = "limit", defaultValue = "3") int limit) { // 可省略，默认 3
        return reportStore.listByConversation(conversationId, userId, limit);
    }
}
