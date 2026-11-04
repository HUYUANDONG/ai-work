package cn.aiworkbench.service.internalapi.feature;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import lombok.Data;

import java.util.List;

/**
 * {@code POST /internal/features/advise}：会签定槽后的建议补数。
 */
@Data
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class FeatureAdviseRequest {

    /** 任务用户，取电商登录态。 */
    private String userId;

    /** 槽位 SKU（通常 ≤5），仅作回显与上下文，板块接口本身无商品粒度。 */
    private List<String> skuIds;

    /** 板块/大盘回看天数，默认 7。 */
    private Integer days;
}
