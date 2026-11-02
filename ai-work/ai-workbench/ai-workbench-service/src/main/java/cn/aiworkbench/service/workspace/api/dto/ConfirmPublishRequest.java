package cn.aiworkbench.service.workspace.api.dto;

import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.Setter;

/**
 * 发起人确认后才允许发送到电商系统。
 */
@Getter
@Setter
public class ConfirmPublishRequest {

    /**
     * 必须为 true，表示发起人已确认当前草稿内容。
     */
    @NotNull
    @AssertTrue(message = "必须确认后再发送")
    private Boolean confirmed;
}
