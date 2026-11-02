package cn.aiworkbench.service.internalapi.feature;

import cn.aiworkbench.service.internalapi.support.InternalApiException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

import java.io.InputStream;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

/**
 * 特征快照内存仓。当前从 classpath fixture 加载，后续可换成电商报表/DB。
 * <p>
 * Java 只提供原始计数/金额，不算分（见 data-contract）。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class FeatureSnapshotStore {

    private final ObjectMapper objectMapper;

    private String snapshotDate = LocalDate.now().toString();
    private final List<Map<String, Object>> items = new ArrayList<>();
    private boolean available;

    /**
     * 启动时加载与 Python 同源的 mock 特征，保证联调口径一致。
     */
    @PostConstruct
    public void load() {
        try {
            ClassPathResource resource = new ClassPathResource("fixtures/mock_features.json");
            try (InputStream in = resource.getInputStream()) {
                Map<String, Object> raw = objectMapper.readValue(in, new TypeReference<>() {
                });
                Object date = raw.get("snapshot_date");
                if (date != null) {
                    snapshotDate = String.valueOf(date);
                }
                Object list = raw.get("items");
                if (list instanceof List<?> rows) {
                    items.clear();
                    for (Object row : rows) {
                        if (row instanceof Map<?, ?> map) {
                            Map<String, Object> copy = new HashMap<>();
                            map.forEach((k, v) -> copy.put(String.valueOf(k), v));
                            items.add(copy);
                        }
                    }
                }
            }
            available = true;
            log.info("feature snapshot loaded date={} rows={}", snapshotDate, items.size());
        } catch (Exception ex) {
            available = false;
            log.error("failed to load fixtures/mock_features.json", ex);
        }
    }

    private void requireAvailable() {
        if (!available) {
            throw InternalApiException.snapshotUnavailable("特征快照不可用");
        }
    }

    /**
     * @return 当前快照日期
     */
    public String snapshotDate() {
        return snapshotDate;
    }

    /**
     * 按条件过滤快照行。
     *
     * @param request 查询条件
     * @return 过滤后的行副本
     */
    public List<Map<String, Object>> query(FeatureQueryRequest request) {
        requireAvailable();
        boolean onSaleOnly = request.getOnSaleOnly() == null || Boolean.TRUE.equals(request.getOnSaleOnly());
        String categoryId = request.getCategoryId();
        List<String> skuIds = request.getSkuIds();
        Set<String> allow = null;
        if (skuIds != null && !skuIds.isEmpty()) {
            if (skuIds.size() > 50) {
                throw InternalApiException.badRequest("sku_ids 最多 50 个");
            }
            allow = new HashSet<>(skuIds);
        }

        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> row : items) {
            if (onSaleOnly && !Boolean.TRUE.equals(row.get("on_sale"))) {
                continue;
            }
            if (categoryId != null && !categoryId.isBlank()
                    && !categoryId.equals(String.valueOf(row.get("category_id")))) {
                continue;
            }
            if (allow != null && !allow.contains(String.valueOf(row.get("sku_id")))) {
                continue;
            }
            result.add(new HashMap<>(row));
        }
        return result;
    }

    /**
     * 按 SKU 取单行。
     *
     * @param skuId SKU
     * @return 行
     */
    public Optional<Map<String, Object>> findBySkuId(String skuId) {
        requireAvailable();
        if (skuId == null || skuId.isBlank()) {
            return Optional.empty();
        }
        return items.stream()
                .filter(row -> skuId.equals(String.valueOf(row.get("sku_id"))))
                .findFirst()
                .map(HashMap::new);
    }
}
