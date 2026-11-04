-- 任务控制位落库，供重启后续领 / 心跳读暂停取消

SET @db := DATABASE();

SET @sql := (
    SELECT IF(
        EXISTS(
            SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = @db
              AND TABLE_NAME = 'ai_task'
              AND COLUMN_NAME = 'pause_requested_at'
        ),
        'SELECT 1',
        'ALTER TABLE ai_task ADD COLUMN pause_requested_at DATETIME(3) NULL COMMENT ''用户请求暂停'' AFTER cancel_requested_at'
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := (
    SELECT IF(
        EXISTS(
            SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = @db
              AND TABLE_NAME = 'ai_task'
              AND COLUMN_NAME = 'pause_reason'
        ),
        'SELECT 1',
        'ALTER TABLE ai_task ADD COLUMN pause_reason VARCHAR(200) NULL COMMENT ''暂停原因'' AFTER pause_requested_at'
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := (
    SELECT IF(
        EXISTS(
            SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = @db
              AND TABLE_NAME = 'ai_task'
              AND COLUMN_NAME = 'cancel_reason'
        ),
        'SELECT 1',
        'ALTER TABLE ai_task ADD COLUMN cancel_reason VARCHAR(200) NULL COMMENT ''取消原因'' AFTER cancel_requested_at'
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
