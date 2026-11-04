package cn.aiworkbench.service.workspace.domain;

import cn.aiworkbench.common.core.error.ErrorCode;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

/**
 * 工作区模块错误码，code 不与 {@link cn.aiworkbench.common.core.error.CommonErrorCode} 重复。
 */
@Getter
@RequiredArgsConstructor
public enum WorkspaceErrorCode implements ErrorCode {

    DRAFT_NOT_FOUND("WORKSPACE_DRAFT_NOT_FOUND", "商品草稿不存在", 404),
    DRAFT_NOT_EDITABLE("WORKSPACE_DRAFT_NOT_EDITABLE", "当前状态的草稿不可编辑", 409),
    DRAFT_NOT_SENDABLE("WORKSPACE_DRAFT_NOT_SENDABLE", "当前状态不可确认上架", 409),
    CONFIRM_REQUIRED("WORKSPACE_CONFIRM_REQUIRED", "必须由发起人确认后才能发送到电商系统", 400),
    PRODUCT_NUMBER_REQUIRED("WORKSPACE_PRODUCT_NUMBER_REQUIRED", "首次发送前必须确定商品编号", 400),
    ECOMMERCE_NOT_READY("WORKSPACE_ECOMMERCE_NOT_READY", "电商系统尚未接入，无法真正创建商品", 503),
    /** 上架商品 / 一键发圈等写回能力暂时砍掉。 */
    FEATURE_TEMPORARILY_CUT(
            "WORKSPACE_FEATURE_TEMPORARILY_CUT",
            "上架商品功能已暂时下线，工作台仅保留爆品分析与质检",
            410);

    private final String code;
    private final String message;
    private final int httpStatus;
}
