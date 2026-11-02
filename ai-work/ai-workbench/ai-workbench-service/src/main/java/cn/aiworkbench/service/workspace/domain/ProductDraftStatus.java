package cn.aiworkbench.service.workspace.domain;

/**
 * 商品草稿状态。后续接入独立操作表后，SENDING / UNKNOWN 会下沉到操作记录。
 */
public enum ProductDraftStatus {

    /** 可编辑，尚未向电商发送。 */
    DRAFT,
    /** 已确认并占位，调用电商进行中。此状态是不可回头点。 */
    SENDING,
    /** 电商已创建成功（含按商品编号核对到已存在）。 */
    SUCCEEDED,
    /** 电商明确拒绝，允许修改后再确认。 */
    FAILED,
    /** 结果不确定，例如超时；再次确认时先按商品编号核对。 */
    UNKNOWN;

    /**
     * 是否允许改内容。
     *
     * @return 可编辑时为 true
     */
    public boolean editable() {
        return this == DRAFT || this == FAILED;
    }

    /**
     * 是否允许发起一次新的电商创建调用。
     *
     * @return 可发送时为 true
     */
    public boolean sendable() {
        return this == DRAFT || this == FAILED || this == UNKNOWN;
    }
}
