CREATE TABLE wb_product_draft (
    id              VARCHAR(32)  NOT NULL COMMENT '草稿 ID',
    user_id         VARCHAR(64)  NOT NULL COMMENT '归属用户',
    product_number  VARCHAR(64)  NULL COMMENT '商品编号，发送核对键',
    title           VARCHAR(200) NOT NULL COMMENT '标题',
    description     VARCHAR(2000) NULL COMMENT '描述',
    status          VARCHAR(32)  NOT NULL COMMENT 'DRAFT/SENDING/SUCCEEDED/FAILED/UNKNOWN',
    target_id       VARCHAR(64)  NULL COMMENT '电商侧商品 ID',
    last_error      VARCHAR(500) NULL COMMENT '最近一次发送错误',
    created_at      DATETIME(3)  NOT NULL COMMENT '创建时间',
    updated_at      DATETIME(3)  NOT NULL COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_wb_product_draft_user_updated (user_id, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='工作台商品草稿';
