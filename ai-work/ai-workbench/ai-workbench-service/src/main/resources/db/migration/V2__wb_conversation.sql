CREATE TABLE wb_conversation (
    id          BIGINT        NOT NULL AUTO_INCREMENT COMMENT '会话 ID，数据库自增',
    user_id     VARCHAR(64)   NOT NULL COMMENT '归属用户',
    title       VARCHAR(200)  NOT NULL COMMENT '窗口标题',
    description VARCHAR(500)  NULL COMMENT '备注',
    created_at  VARCHAR(64)   NOT NULL COMMENT '创建时间',
    updated_at  VARCHAR(64)   NOT NULL COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_wb_conversation_user_updated (user_id, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='聊天窗口';
