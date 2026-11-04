-- 会话长期记忆槽位 + 消息意图字段（无向量；结构化 LTM）
-- 幂等：列已存在则跳过（避免手工补列后 Flyway 再跑失败）

SET @db := DATABASE();

SET @sql := (
    SELECT IF(
        EXISTS(
            SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = @db
              AND TABLE_NAME = 'ai_conversation'
              AND COLUMN_NAME = 'session_state_json'
        ),
        'SELECT 1',
        'ALTER TABLE ai_conversation ADD COLUMN session_state_json JSON NULL COMMENT ''LTM 槽位：last_intent/last_task/active_task/advice_offer_pending'' AFTER title'
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
              AND TABLE_NAME = 'ai_message'
              AND COLUMN_NAME = 'intent'
        ),
        'SELECT 1',
        'ALTER TABLE ai_message ADD COLUMN intent VARCHAR(32) NULL COMMENT ''助手轮意图，user 轮为空'' AFTER content'
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
