package cn.aiworkbench.service.internalapi.support;

import lombok.AllArgsConstructor;
import lombok.Getter;

/**
 * 内部 API 契约错误体：{@code {"code","message"}}。
 */
@Getter
@AllArgsConstructor
public class InternalErrorBody {

    private final String code;
    private final String message;
}
