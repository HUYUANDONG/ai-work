package cn.aiworkbench.service.integration.outfitadmin;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;

import java.net.http.HttpClient;
import java.time.Duration;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 调用电商后台 reportStat：商品销量、日板块流量、日流量大盘。
 */
@Slf4j
@Component
public class OutfitAdminReportClient {

    public static final String GOODS_STAT_PATH = "outfit-admin/reportStat/goodsStatList";
    public static final String DAILY_PLATE_PATH = "outfit-admin/reportStat/dailyPlateList";
    public static final String DAILY_DATA_PATH = "outfit-admin/reportStat/dailyDataList";
    private static final int SUCCESS_CODE = 2000;
    private static final DateTimeFormatter FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final ZoneId ZONE = ZoneId.of("Asia/Shanghai");

    private final RestClient restClient;
    private final ObjectMapper objectMapper;
    private final int pageSize;
    private final int maxPages;

    /**
     * @param restClientBuilder Boot RestClient
     * @param objectMapper      JSON
     * @param baseUrl           如 https://adminapi.hpsmall.com
     * @param pageSize          分页
     * @param maxPages          最多页数
     */
    public OutfitAdminReportClient(
            RestClient.Builder restClientBuilder,
            ObjectMapper objectMapper,
            @Value("${wb.admin.api-base:https://adminapi.hpsmall.com}") String baseUrl,
            @Value("${wb.admin.page-size:100}") int pageSize,
            @Value("${wb.admin.max-pages:30}") int maxPages) {
        this.objectMapper = objectMapper;
        this.pageSize = Math.max(pageSize, 20);
        this.maxPages = Math.max(maxPages, 1);
        HttpClient httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(5))
                .build();
        JdkClientHttpRequestFactory factory = new JdkClientHttpRequestFactory(httpClient);
        factory.setReadTimeout(Duration.ofSeconds(25));
        this.restClient = restClientBuilder
                .baseUrl(baseUrl.replaceAll("/$", ""))
                .requestFactory(factory)
                .build();
        log.info("outfit-admin report client baseUrl={}", baseUrl);
    }

    /**
     * 拉取当前窗与对比窗商品销量，聚合成快照行。
     *
     * @param credential 加签凭证
     * @param windowDays 窗口天数
     * @return 快照行
     */
    public List<Map<String, Object>> loadGoodsSnapshots(EcommerceCredential credential, int windowDays) {
        int days = Math.max(windowDays, 1);
        LocalDateTime end = LocalDateTime.now(ZONE);
        LocalDateTime start = end.minusDays(days);
        LocalDateTime prevEnd = start;
        LocalDateTime prevStart = start.minusDays(days);
        List<Map<String, Object>> current = fetchRange(credential, start, end);
        List<Map<String, Object>> previous = fetchRange(credential, prevStart, prevEnd);
        log.info("goodsStatList current={} previous={} days={}", current.size(), previous.size(), days);
        return GoodsStatSnapshotMapper.mergeWindows(current, previous);
    }

    /**
     * 建议阶段：日板块流量 + 可选大盘摘要。
     *
     * @param credential 凭证
     * @param days       回看天数
     * @return plates / store
     */
    public Map<String, Object> loadAdviseContext(EcommerceCredential credential, int days) {
        int window = Math.max(days, 1);
        LocalDateTime end = LocalDateTime.now(ZONE);
        LocalDateTime start = end.minusDays(window);
        List<Map<String, Object>> platesRaw = fetchRange(credential, DAILY_PLATE_PATH, start, end);
        List<Map<String, Object>> storeRaw;
        try {
            storeRaw = fetchRange(credential, DAILY_DATA_PATH, start, end);
        } catch (Exception ex) {
            log.warn("dailyDataList skipped: {}", ex.getMessage());
            storeRaw = List.of();
        }
        List<Map<String, Object>> plates = AdviseContextMapper.slimPlates(platesRaw, 12);
        Map<String, Object> store = AdviseContextMapper.slimStore(storeRaw);
        log.info("advise plates={} storeKeys={}", plates.size(), store.size());
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("plates", plates);
        out.put("store", store);
        return out;
    }

    private List<Map<String, Object>> fetchRange(
            EcommerceCredential credential, LocalDateTime start, LocalDateTime end) {
        return fetchRange(credential, GOODS_STAT_PATH, start, end);
    }

    private List<Map<String, Object>> fetchRange(
            EcommerceCredential credential,
            String routePath,
            LocalDateTime start,
            LocalDateTime end) {
        List<Map<String, Object>> all = new ArrayList<>();
        int total = Integer.MAX_VALUE;
        int pages = routePath.equals(GOODS_STAT_PATH) ? maxPages : Math.min(maxPages, 5);
        for (int page = 1; page <= pages && all.size() < total; page++) {
            Map<String, Object> business = new LinkedHashMap<>();
            business.put("pageNum", page);
            business.put("pageSize", pageSize);
            business.put("startTime", start.format(FMT));
            business.put("endTime", end.format(FMT));
            Map<String, String> form = OutfitAdminSigner.sign(
                    routePath,
                    business,
                    credential.token(),
                    credential.secretKey(),
                    System.currentTimeMillis(),
                    OutfitAdminSigner.newSeed());
            JsonNode root = postForm(routePath, form);
            int code = root.path("resultCode").asInt();
            if (code != SUCCESS_CODE) {
                throw new IllegalStateException(
                        routePath + " resultCode=" + code + " msg=" + root.path("resultMsg").asText());
            }
            JsonNode data = root.path("data");
            JsonNode listNode = data.has("list") ? data.path("list") : data;
            if (data.has("total")) {
                total = data.path("total").asInt(all.size());
            }
            if (!listNode.isArray() || listNode.isEmpty()) {
                break;
            }
            for (JsonNode item : listNode) {
                @SuppressWarnings("unchecked")
                Map<String, Object> row = objectMapper.convertValue(item, Map.class);
                all.add(row);
            }
            if (listNode.size() < pageSize) {
                break;
            }
        }
        return all;
    }

    private JsonNode postForm(String routePath, Map<String, String> form) {
        MultiValueMap<String, String> body = new LinkedMultiValueMap<>();
        form.forEach(body::add);
        String raw = restClient.post()
                .uri("/" + routePath)
                .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                .body(body)
                .retrieve()
                .body(String.class);
        try {
            return objectMapper.readTree(raw == null ? "{}" : raw);
        } catch (Exception ex) {
            throw new IllegalStateException("解析 " + routePath + " 失败", ex);
        }
    }
}
