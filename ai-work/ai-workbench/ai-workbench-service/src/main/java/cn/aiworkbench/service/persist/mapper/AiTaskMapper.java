package cn.aiworkbench.service.persist.mapper;

import cn.aiworkbench.service.persist.infra.AiTaskDO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * 任务表 Mapper：队列权威（入队 / SKIP LOCKED 领取 / 心跳 / 终态）。
 * SQL 见 {@code classpath:mapper/AiTaskMapper.xml}。
 */
@Mapper
public interface AiTaskMapper {

    /**
     * 入队（已存在则更新输入）。
     *
     * @param row 任务
     * @return 行数
     */
    int upsertQueued(AiTaskDO row);

    /**
     * 锁一行可领取任务：QUEUED，或租约已过期的 RUNNING。
     *
     * @param types 类型
     * @return 行或 null
     */
    AiTaskDO lockClaimable(@Param("types") List<String> types);

    /**
     * 领取为 RUNNING。
     *
     * @param taskId       任务
     * @param runId        本次 run
     * @param leaseToken   租约
     * @param workerId     Worker
     * @param workflow     工作流版本
     * @param leaseSeconds 租约秒数
     * @return 行数
     */
    int markRunning(
            @Param("taskId") String taskId,
            @Param("runId") String runId,
            @Param("leaseToken") String leaseToken,
            @Param("workerId") String workerId,
            @Param("workflow") String workflow,
            @Param("leaseSeconds") int leaseSeconds);

    /**
     * 心跳续租。
     *
     * @param taskId       任务
     * @param leaseToken   租约
     * @param leaseSeconds 续租秒数
     * @return 行数
     */
    int heartbeat(
            @Param("taskId") String taskId,
            @Param("leaseToken") String leaseToken,
            @Param("leaseSeconds") int leaseSeconds);

    /**
     * 请求取消。
     *
     * @param taskId 任务
     * @param reason 原因
     * @return 行数
     */
    int markCancelRequested(@Param("taskId") String taskId, @Param("reason") String reason);

    /**
     * 请求暂停。
     *
     * @param taskId 任务
     * @param reason 原因
     * @return 行数
     */
    int markPauseRequested(@Param("taskId") String taskId, @Param("reason") String reason);

    /**
     * 按 ID 读一行。
     *
     * @param taskId 任务
     * @return 行
     */
    AiTaskDO selectByTaskId(@Param("taskId") String taskId);

    /**
     * 写终态。
     *
     * @param row 终态字段
     * @return 行数
     */
    int markFinished(AiTaskDO row);
}
