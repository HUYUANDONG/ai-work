package cn.aiworkbench.service.internalapi.feature;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 特征查询内部 API（Python 爆品/质检筛选依赖）。
 */
@Tag(name = "Internal Features")
@RestController
@RequestMapping("/internal")
@RequiredArgsConstructor
public class FeatureController {

    private final FeatureService featureService;

    /**
     * 批量特征查询。
     *
     * @param request 条件
     * @return 快照行
     */
    @Operation(summary = "批量特征 query")
    @PostMapping("/features/query")
    public FeatureQueryResponse query(@RequestBody(required = false) FeatureQueryRequest request) {
        return featureService.query(request);
    }

    /**
     * 单品特征。
     *
     * @param skuId    SKU
     * @param statDate 可选统计日
     * @return 单行
     */
    @Operation(summary = "单品特征")
    @GetMapping("/products/{skuId}/features")
    public ProductFeatureResponse productFeatures(
            @PathVariable String skuId,
            @RequestParam(value = "stat_date", required = false) String statDate) {
        return featureService.getProduct(skuId, statDate);
    }
}
