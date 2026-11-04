/**
 * 爆品 / 质检报告内部接口（给 Python Worker 回写，给追问回读）。
 *
 * <p>读代码顺序：{@link cn.aiworkbench.service.internalapi.report.ReportController}
 * → {@link cn.aiworkbench.service.internalapi.report.InMemoryReportStore}
 * → {@link cn.aiworkbench.service.persist.ReportPersistService}
 * → {@link cn.aiworkbench.service.persist.mapper.AiExplosionMapper}。
 *
 * <p>Java 没有 Python 装饰器，相近机制叫<strong>注解</strong>（Annotation）。
 * 注解本身几乎不执行逻辑，是给框架「贴标签」：Spring 扫到 {@code @RestController} 才把它当 HTTP 接口；
 * MyBatis 扫到 {@code @Mapper} 后，再按接口方法名去 {@code resources/mapper/*.xml} 里找同名 SQL。
 * 本项目约定：SQL 一律写 XML，不在接口上堆 {@code @Select}/{@code @Insert}。
 */
package cn.aiworkbench.service.internalapi.report;
