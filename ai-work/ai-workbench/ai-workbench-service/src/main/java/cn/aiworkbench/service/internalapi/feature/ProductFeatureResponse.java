package cn.aiworkbench.service.internalapi.feature;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import lombok.Builder;
import lombok.Data;

import java.util.Map;

/**
 * 单品特征响应。
 */
@Data
@Builder
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class ProductFeatureResponse {

    private String snapshotDate;
    private Map<String, Object> item;
}
