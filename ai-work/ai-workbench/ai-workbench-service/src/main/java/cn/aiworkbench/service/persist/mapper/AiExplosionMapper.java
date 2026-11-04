package cn.aiworkbench.service.persist.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;
import java.util.Map;

/**
 * 爆品报告 Mapper：头表 {@code ai_explosion_analysis}，行表 {@code ai_explosion_item}。
 *
 * <p>接口只声明方法；SQL 在 {@code classpath:mapper/AiExplosionMapper.xml}。
 * {@code namespace} = 本接口全名，{@code id} = 方法名。
 *
 * <p>注解：
 * <ul>
 *   <li>{@code @Mapper} — MyBatis，配合 {@code @MapperScan} 注册成 Spring Bean。</li>
 *   <li>{@code @Param} — MyBatis，多参数时给 XML 里 {@code #{taskId}} 起名；单参数且名字能对上也建议写上。</li>
 * </ul>
 * 不再在接口上写 {@code @Insert}/{@code @Select}，项目约定 SQL 统一进 XML。
 */
@Mapper
public interface AiExplosionMapper {

    /**
     * 覆盖写入报告头。{@code ON DUPLICATE KEY UPDATE}：task_id 已存在则改。
     *
     * @param taskId         任务
     * @param userId         用户
     * @param conversationId 会话
     * @param snapshotDate   快照日
     * @param scoringVersion 评分版本
     * @param councilVersion 会签版本
     * @param timeWindowDays 窗口
     * @param topN           TopN
     * @param itemCount      行数
     * @param goalMode       目标
     * @param focusSlots     槽位数
     * @param planDegraded   是否降级（0/1）
     * @param focusCount     进槽数
     * @param summary        摘要
     * @param headerJson     完整头 JSON
     * @return 影响行数
     */
    int upsertHeader(
            @Param("taskId") String taskId,
            @Param("userId") String userId,
            @Param("conversationId") String conversationId,
            @Param("snapshotDate") String snapshotDate,
            @Param("scoringVersion") String scoringVersion,
            @Param("councilVersion") String councilVersion,
            @Param("timeWindowDays") Integer timeWindowDays,
            @Param("topN") Integer topN,
            @Param("itemCount") Integer itemCount,
            @Param("goalMode") String goalMode,
            @Param("focusSlots") Integer focusSlots,
            @Param("planDegraded") int planDegraded,
            @Param("focusCount") Integer focusCount,
            @Param("summary") String summary,
            @Param("headerJson") String headerJson);

    /**
     * 清空该任务下旧 SKU 行。
     *
     * @param taskId 任务
     * @return 删除行数
     */
    int deleteItems(@Param("taskId") String taskId);

    /**
     * 写入 / 覆盖一行爆品 SKU。
     *
     * @param taskId  任务
     * @param skuId   SKU
     * @param rankNo  排名
     * @param score   爆品分
     * @param bucket  动作分型
     * @param action  主动作
     * @param inSlot  是否进槽（0/1）
     * @param risk    质检风险
     * @param excerpt 特征摘录 JSON
     * @param council 会签摘录 JSON
     * @param reason  理由
     * @return 影响行数
     */
    int upsertItem(
            @Param("taskId") String taskId,
            @Param("skuId") String skuId,
            @Param("rankNo") Integer rankNo,
            @Param("score") Double score,
            @Param("bucket") String bucket,
            @Param("action") String action,
            @Param("inSlot") int inSlot,
            @Param("risk") String risk,
            @Param("excerpt") String excerpt,
            @Param("council") String council,
            @Param("reason") String reason);

    /**
     * 某会话下爆品报告头，新的在前。
     *
     * @param conversationId 会话
     * @param userId         用户
     * @param limit          条数
     * @return 头行 Map
     */
    List<Map<String, Object>> listHeaders(
            @Param("conversationId") String conversationId,
            @Param("userId") String userId,
            @Param("limit") int limit);

    /**
     * 某任务下的爆品 SKU 行，按排名。
     *
     * @param taskId 任务
     * @return 商品行
     */
    List<Map<String, Object>> listItems(@Param("taskId") String taskId);
}
