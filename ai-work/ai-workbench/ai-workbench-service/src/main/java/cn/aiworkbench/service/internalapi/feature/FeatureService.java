package cn.aiworkbench.service.internalapi.feature;

import cn.aiworkbench.service.integration.outfitadmin.EcommerceCredential;
import cn.aiworkbench.service.integration.outfitadmin.EcommerceCredentialStore;
import cn.aiworkbench.service.integration.outfitadmin.OutfitAdminReportClient;
import cn.aiworkbench.service.internalapi.support.InternalApiException;
import cn.hutool.core.util.StrUtil;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

/**
 * 爆品筛选主依赖：优先电商 goodsStatList，失败再按开关回落 fixture。
 */
@Slf4j
@Service
public class FeatureService {

    private final FeatureSnapshotStore store;
    private final OutfitAdminReportClient reportClient;
    private final EcommerceCredentialStore credentialStore;
    private final boolean allowFixture;

    /**
     * @param store            fixture 仓
     * @param reportClient     电商报表客户端
     * @param credentialStore  登录态
     * @param allowFixture     无凭证或接口失败时是否回落示例数据
     */
    public FeatureService(
            FeatureSnapshotStore store,
            OutfitAdminReportClient reportClient,
            EcommerceCredentialStore credentialStore,
            @Value("${wb.admin.allow-fixture:false}") boolean allowFixture) {
        this.store = store;
        this.reportClient = reportClient;
        this.credentialStore = credentialStore;
        this.allowFixture = allowFixture;
    }

    /**
     * 批量查询快照特征（默认 profile=score，不含板块/大盘）。
     *
     * @param request 条件
     * @return 响应
     */
    public FeatureQueryResponse query(FeatureQueryRequest request) {
        FeatureQueryRequest safe = request == null ? new FeatureQueryRequest() : request;
        String profile = StrUtil.blankToDefault(safe.getProfile(), "score").trim().toLowerCase();
        if (!"score".equals(profile)) {
            log.warn("features/query profile={} ignored; use /features/advise for advise context", profile);
        }
        int days = safe.getTimeWindowDays() == null ? 30 : Math.max(safe.getTimeWindowDays(), 1);
        Optional<EcommerceCredential> credential = credentialStore.find(safe.getUserId());
        if (credential.isPresent()) {
            try {
                List<Map<String, Object>> items = filterLive(reportClient.loadGoodsSnapshots(credential.get(), days), safe);
                return FeatureQueryResponse.builder()
                        .snapshotDate(LocalDate.now().toString())
                        .rowCount(items.size())
                        .items(items)
                        .source("goodsStatList")
                        .amountUnit("yuan")
                        .build();
            } catch (Exception ex) {
                log.error("goodsStatList failed userId={}", safe.getUserId(), ex);
                if (!allowFixture) {
                    return FeatureQueryResponse.builder()
                            .snapshotDate(LocalDate.now().toString())
                            .rowCount(0)
                            .items(List.of())
                            .source("error")
                            .message(ex.getMessage())
                            .build();
                }
            }
        } else if (!allowFixture) {
            return FeatureQueryResponse.builder()
                    .snapshotDate(LocalDate.now().toString())
                    .rowCount(0)
                    .items(List.of())
                    .source("no_credentials")
                    .message("缺少电商登录 token，无法拉取 goodsStatList。请在工作台已登录状态下重新发起分析。")
                    .build();
        }
        List<Map<String, Object>> fixture = store.query(safe);
        return FeatureQueryResponse.builder()
                .snapshotDate(resolveSnapshotDate(safe.getStatDate()))
                .rowCount(fixture.size())
                .items(fixture)
                .source("fixture")
                .build();
    }

    /**
     * 建议阶段辅源：日板块流量 + 可选大盘（定槽后再调）。
     *
     * @param request 槽位与用户
     * @return 板块与大盘
     */
    @SuppressWarnings("unchecked")
    public FeatureAdviseResponse advise(FeatureAdviseRequest request) {
        FeatureAdviseRequest safe = request == null ? new FeatureAdviseRequest() : request;
        List<String> skuIds = safe.getSkuIds() == null ? List.of() : safe.getSkuIds().stream()
                .filter(StrUtil::isNotBlank)
                .limit(10)
                .toList();
        int days = safe.getDays() == null ? 7 : Math.max(safe.getDays(), 1);
        Optional<EcommerceCredential> credential = credentialStore.find(safe.getUserId());
        if (credential.isEmpty()) {
            return FeatureAdviseResponse.builder()
                    .skuIds(skuIds)
                    .plates(List.of())
                    .store(Map.of())
                    .source("no_credentials")
                    .message("缺少电商登录 token，无法拉取日板块流量。")
                    .build();
        }
        try {
            Map<String, Object> ctx = reportClient.loadAdviseContext(credential.get(), days);
            List<Map<String, Object>> plates = (List<Map<String, Object>>) ctx.getOrDefault("plates", List.of());
            Map<String, Object> store = (Map<String, Object>) ctx.getOrDefault("store", Map.of());
            return FeatureAdviseResponse.builder()
                    .skuIds(skuIds)
                    .plates(plates)
                    .store(store)
                    .source("dailyPlateList")
                    .build();
        } catch (Exception ex) {
            log.error("features/advise failed userId={}", safe.getUserId(), ex);
            return FeatureAdviseResponse.builder()
                    .skuIds(skuIds)
                    .plates(List.of())
                    .store(Map.of())
                    .source("error")
                    .message(ex.getMessage())
                    .build();
        }
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

    private List<Map<String, Object>> filterLive(List<Map<String, Object>> items, FeatureQueryRequest request) {
        List<String> skuIds = request.getSkuIds();
        Set<String> allow = null;
        if (skuIds != null && !skuIds.isEmpty()) {
            allow = new HashSet<>();
            for (String skuId : skuIds) {
                if (StrUtil.isNotBlank(skuId)) {
                    allow.add(skuId);
                }
            }
        }
        if (allow == null) {
            return items;
        }
        List<Map<String, Object>> filtered = new ArrayList<>();
        for (Map<String, Object> row : items) {
            if (allow.contains(String.valueOf(row.get("sku_id")))) {
                filtered.add(row);
            }
        }
        return filtered;
    }

    private String resolveSnapshotDate(String statDate) {
        if (statDate != null && !statDate.isBlank()) {
            return statDate;
        }
        return store.snapshotDate();
    }
}
