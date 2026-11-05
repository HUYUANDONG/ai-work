package cn.aiworkbench.service.conversation.infra;

import lombok.Getter;
import lombok.Setter;

/**
 * {@code ai_long_memory} 表行。
 */
@Getter
@Setter
public class AiLongMemoryDO {

    private Long id;
    private String scope;
    private String ownerId;
    private String memKey;
    private String memValue;
    private String source;
}
