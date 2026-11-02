package cn.aiworkbench.common.core.web;

import lombok.Getter;
import lombok.Setter;

/**
 * 分页查询参数。所有列表接口必须分页，禁止无界查询。
 */
@Getter
@Setter
public class PageQuery {

    private static final int DEFAULT_PAGE_NO = 1;
    private static final int DEFAULT_PAGE_SIZE = 20;
    private static final int MAX_PAGE_SIZE = 100;

    /**
     * 页码，从 1 开始。
     */
    private int pageNo = DEFAULT_PAGE_NO;

    /**
     * 每页条数，上限 100。
     */
    private int pageSize = DEFAULT_PAGE_SIZE;

    /**
     * 计算 SQL OFFSET。
     *
     * @return 偏移量
     */
    public int offset() {
        return (pageNo - 1) * pageSize;
    }
}
