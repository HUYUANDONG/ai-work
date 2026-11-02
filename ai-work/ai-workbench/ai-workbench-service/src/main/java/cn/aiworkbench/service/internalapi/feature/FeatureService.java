package cn.aiworkbench.service.internalapi.feature;

import cn.aiworkbench.service.internalapi.support.InternalApiException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * 爆品筛选主依赖：批量/单品特征查询。
 */
@Service
@RequiredArgsConstructor
public class FeatureService {

    private final FeatureSnapshotStore store;

    /**
     * 批量查询快照特征。
     *
     * @param request 条件
     * @return 响应
     */
    public FeatureQueryResponse query(FeatureQueryRequest request) {
        FeatureQueryRequest safe = request == null ? new FeatureQueryRequest() : request;
        List<Map<String, Object>> items = store.query(safe);
        return FeatureQueryResponse.builder()
                .snapshotDate(resolveSnapshotDate(safe.getStatDate()))
                .rowCount(items.size())
                .items(items)
                .build();
    }

    /**
     * 单品特征。
     *
     * @param skuId    SKU
     * @param statDate 可选统计日
     * @return 响应
     */
    public ProductFeatureResponse getProduct(String skuId, String statDate) {
        Map<String, Object> item = store.findBySkuId(skuId)
                .orElseThrow(() -> InternalApiException.notFound("sku not found: " + skuId));
        return ProductFeatureResponse.builder()
                .snapshotDate(resolveSnapshotDate(statDate))
                .item(item)
                .build();
    }

    private String resolveSnapshotDate(String statDate) {
        if (statDate != null && !statDate.isBlank()) {
            return statDate;
        }
        return store.snapshotDate();
    }
}
