-- 跨会话长期记忆：SYSTEM=全站事实，USER=运营画像。与会话槽位 session_state_json 分开。

CREATE TABLE ai_long_memory (
    id          BIGINT       NOT NULL AUTO_INCREMENT,
    scope       VARCHAR(16)  NOT NULL COMMENT 'SYSTEM / USER',
    owner_id    VARCHAR(64)  NOT NULL COMMENT 'SYSTEM 固定 global；USER 为 user_id',
    mem_key     VARCHAR(64)  NOT NULL COMMENT '如 business_line、margin_min',
    mem_value   VARCHAR(1000) NOT NULL COMMENT '纯文本或数字字符串',
    source      VARCHAR(32)  NULL COMMENT 'seed / utterance',
    updated_at  DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_ai_long_memory (scope, owner_id, mem_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='长期记忆';

INSERT INTO ai_long_memory (scope, owner_id, mem_key, mem_value, source)
VALUES ('SYSTEM', 'global', 'business_line', '公司主营户外运动服饰', 'seed');
