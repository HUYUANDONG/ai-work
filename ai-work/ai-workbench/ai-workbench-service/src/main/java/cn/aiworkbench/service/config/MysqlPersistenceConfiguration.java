package cn.aiworkbench.service.config;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Configuration;
import org.springframework.transaction.annotation.EnableTransactionManagement;

/**
 * MySQL 启用时扫描 Mapper 并打开事务。
 */
@Configuration
@ConditionalOnProperty(name = "wb.mysql.enabled", havingValue = "true")
@MapperScan({
        "cn.aiworkbench.service.workspace.mapper",
        "cn.aiworkbench.service.conversation.mapper",
        "cn.aiworkbench.service.persist.mapper"
})
@EnableTransactionManagement
public class MysqlPersistenceConfiguration {
}
