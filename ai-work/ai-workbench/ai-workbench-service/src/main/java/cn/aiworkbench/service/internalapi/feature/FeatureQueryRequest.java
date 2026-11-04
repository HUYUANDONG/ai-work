package cn.aiworkbench.service.internalapi.feature;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import lombok.Data;

import java.util.List;

/**
 * {@code POST /internal/features/query} 请求体。
 */
@Data
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class FeatureQueryRequest {

    /** 统计日，默认当天快照。 */
    private String statDate;

    /** 是否仅在售，默认 true。 */
    private Boolean onSaleOnly = Boolean.TRUE;

    /** 类目过滤。 */
    private String categoryId;

    /** 指定 SKU 列表（质检批量 ≤50）。 */
    private List<String> skuIds;

    /** 任务所属用户，用来取电商登录态。 */
    private String userId;

    /** 当前窗口天数，默认 30。 */
    private Integer timeWindowDays;

    /**
     * 投影档：{@code score}（选品/打分，默认）不带板块/大盘。
     * 建议阶段请走 {@code /internal/features/advise}。
     */
    private String profile = "score";
}
