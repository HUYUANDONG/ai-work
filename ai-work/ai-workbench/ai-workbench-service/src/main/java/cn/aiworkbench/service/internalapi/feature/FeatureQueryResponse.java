package cn.aiworkbench.service.internalapi.feature;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import lombok.Builder;
import lombok.Data;

import java.util.List;
import java.util.Map;

/**
 * 批量特征查询响应。
 */
@Data
@Builder
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class FeatureQueryResponse {

    private String snapshotDate;
    private int rowCount;
    private List<Map<String, Object>> items;
    /** fixture / goodsStatList / no_credentials / error */
    private String source;
    /**
     * 金额单位（元/分），挂在响应级，避免每行重复。
     */
    private String amountUnit;
    private String message;
}
