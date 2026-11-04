package cn.aiworkbench.service.internalapi.feature;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import lombok.Builder;
import lombok.Data;

import java.util.List;
import java.util.Map;

/**
 * 建议阶段辅源：日板块流量 + 可选大盘摘要。
 */
@Data
@Builder
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class FeatureAdviseResponse {

    /** 回显槽位 SKU。 */
    private List<String> skuIds;

    /** dailyPlateList 精简行。 */
    private List<Map<String, Object>> plates;

    /** dailyDataList 一行摘要；可能为空。 */
    private Map<String, Object> store;

    /** dailyPlateList / no_credentials / error / fixture */
    private String source;

    /** 失败说明。 */
    private String message;
}
