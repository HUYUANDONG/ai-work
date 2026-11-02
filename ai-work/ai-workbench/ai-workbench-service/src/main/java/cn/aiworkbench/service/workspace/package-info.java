/**
 * 草稿与工作区。本模块先落地「商品草稿 + 确认后发送」作为写法样例：
 * api 只暴露 HTTP，application 写用例，domain 守状态；
 * {@link cn.aiworkbench.service.workspace.mapper.ProductDraftMapper} 访问表，
 * {@link cn.aiworkbench.service.workspace.infra.MyBatisProductDraftRepository} 把行转成领域对象。
 * 未开 MySQL 时由内存仓储顶上。电商副作用只经过
 * {@link cn.aiworkbench.service.integration.ecommerce.EcommerceAdapter}。
 */
package cn.aiworkbench.service.workspace;
