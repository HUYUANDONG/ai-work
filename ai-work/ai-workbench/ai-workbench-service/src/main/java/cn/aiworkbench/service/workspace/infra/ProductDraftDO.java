package cn.aiworkbench.service.workspace.infra;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Getter;
import lombok.Setter;

import java.time.Instant;

/**
 * 商品草稿表映射，只服务持久化，不含业务规则。
 */
@Getter
@Setter
@TableName("wb_product_draft")
public class ProductDraftDO {

    /**
     * 主键，由领域对象生成后写入。
     */
    @TableId(type = IdType.INPUT)
    private String id;

    private String userId;

    private String productNumber;

    private String title;

    private String description;

    private String status;

    private String targetId;

    private String lastError;

    private Instant createdAt;

    private Instant updatedAt;
}
