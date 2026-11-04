package cn.aiworkbench.service.persist.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

/**
 * {@code ai_run} Mapper。SQL 见 {@code classpath:mapper/AiRunMapper.xml}。
 */
@Mapper
public interface AiRunMapper {

    /**
     * 新建一次执行。
     *
     * @param runId      run
     * @param taskId     任务
     * @param leaseToken 租约
     * @param workerId   Worker
     * @return 行数
     */
    int insertRunning(
            @Param("runId") String runId,
            @Param("taskId") String taskId,
            @Param("leaseToken") String leaseToken,
            @Param("workerId") String workerId);

    /**
     * 结束一次执行。
     *
     * @param runId        run
     * @param status       SUCCEEDED/FAILED/TIMEOUT
     * @param errorCode    错误码
     * @param errorMessage 说明
     * @return 行数
     */
    int markFinished(
            @Param("runId") String runId,
            @Param("status") String status,
            @Param("errorCode") String errorCode,
            @Param("errorMessage") String errorMessage);
}
