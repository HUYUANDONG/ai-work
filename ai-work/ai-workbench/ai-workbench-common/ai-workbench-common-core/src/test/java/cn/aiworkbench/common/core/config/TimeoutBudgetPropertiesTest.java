package cn.aiworkbench.common.core.config;

import org.junit.jupiter.api.Test;

import java.time.Duration;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;

/**
 * 超时预算大小关系校验。
 */
class TimeoutBudgetPropertiesTest {

    @Test
    void defaultValuesShouldPass() {
        TimeoutBudgetProperties properties = new TimeoutBudgetProperties();
        assertDoesNotThrow(properties::validate);
    }

    @Test
    void innerTimeoutMustBeSmallerThanOuter() {
        TimeoutBudgetProperties properties = new TimeoutBudgetProperties();
        properties.setJavaExecuteOperation(Duration.ofSeconds(10));
        properties.setEcommerceMutation(Duration.ofSeconds(20));
        assertThrows(IllegalStateException.class, properties::validate);
    }
}
