package cn.aiworkbench.common.core.web;

import lombok.Getter;
import lombok.Setter;

import java.util.Collections;
import java.util.List;

/**
 * 分页结果。
 *
 * @param <T> 记录类型
 */
@Getter
@Setter
public class PageResult<T> {

    private long total;
    private int pageNo;
    private int pageSize;
    private List<T> records = Collections.emptyList();

    /**
     * 构造空分页。
     *
     * @param pageNo   页码
     * @param pageSize 每页条数
     * @param <T>      记录类型
     * @return 空分页
     */
    public static <T> PageResult<T> empty(int pageNo, int pageSize) {
        PageResult<T> result = new PageResult<>();
        result.setPageNo(pageNo);
        result.setPageSize(pageSize);
        result.setTotal(0L);
        result.setRecords(Collections.emptyList());
        return result;
    }

    /**
     * 构造分页结果。
     *
     * @param pageNo   页码
     * @param pageSize 每页条数
     * @param total    总条数
     * @param records  当前页记录
     * @param <T>      记录类型
     * @return 分页结果
     */
    public static <T> PageResult<T> of(int pageNo, int pageSize, long total, List<T> records) {
        PageResult<T> result = new PageResult<>();
        result.setPageNo(pageNo);
        result.setPageSize(pageSize);
        result.setTotal(total);
        result.setRecords(records == null ? Collections.emptyList() : records);
        return result;
    }
}
