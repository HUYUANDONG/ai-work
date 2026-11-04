package cn.aiworkbench.service.persist.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;
import java.util.Map;

/**
 * 质检报告 Mapper。SQL 见 {@code classpath:mapper/AiQualityMapper.xml}。
 */
@Mapper
public interface AiQualityMapper {

    /**
     * 覆盖写入质检头。
     *
     * @param taskId         任务
     * @param userId         用户
     * @param conversationId 会话
     * @param snapshotDate   快照日
     * @param scoringVersion 版本
     * @param skuCount       SKU 数
     * @param highRiskCount  高风险数
     * @param summary        摘要
     * @param headerJson     头 JSON
     * @return 行数
     */
    int upsertHeader(
            @Param("taskId") String taskId,
            @Param("userId") String userId,
            @Param("conversationId") String conversationId,
            @Param("snapshotDate") String snapshotDate,
            @Param("scoringVersion") String scoringVersion,
            @Param("skuCount") Integer skuCount,
            @Param("highRiskCount") Integer highRiskCount,
            @Param("summary") String summary,
            @Param("headerJson") String headerJson);

    /**
     * 清空任务下行。
     *
     * @param taskId 任务
     * @return 行数
     */
    int deleteItems(@Param("taskId") String taskId);

    /**
     * 写入问题行。
     *
     * @param taskId     任务
     * @param skuId      SKU
     * @param qScore     质检分
     * @param opsScore   运营分
     * @param risk       风险
     * @param expScore   爆品分
     * @param candidate  是否爆品候选
     * @param issuesJson 问题 JSON
     * @param skipped    跳过规则
     * @param excerpt    特征
     * @return 行数
     */
    int upsertItem(
            @Param("taskId") String taskId,
            @Param("skuId") String skuId,
            @Param("qScore") Double qScore,
            @Param("opsScore") Double opsScore,
            @Param("risk") String risk,
            @Param("expScore") Double expScore,
            @Param("candidate") Integer candidate,
            @Param("issuesJson") String issuesJson,
            @Param("skipped") String skipped,
            @Param("excerpt") String excerpt);

    /**
     * 会话下质检头。
     *
     * @param conversationId 会话
     * @param userId         用户
     * @param limit          条数
     * @return 头
     */
    List<Map<String, Object>> listHeaders(
            @Param("conversationId") String conversationId,
            @Param("userId") String userId,
            @Param("limit") int limit);

    /**
     * 任务下问题行。
     *
     * @param taskId 任务
     * @return 行
     */
    List<Map<String, Object>> listItems(@Param("taskId") String taskId);
}
