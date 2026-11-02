package cn.aiworkbench.service.rpc;

import cn.aiworkbench.common.logging.trace.TraceConstants;
import org.apache.dubbo.common.constants.CommonConstants;
import org.apache.dubbo.common.extension.Activate;
import org.apache.dubbo.rpc.Filter;
import org.apache.dubbo.rpc.Invocation;
import org.apache.dubbo.rpc.Invoker;
import org.apache.dubbo.rpc.Result;
import org.apache.dubbo.rpc.RpcContext;
import org.apache.dubbo.rpc.RpcException;
import org.slf4j.MDC;

/**
 * 将 Trace ID 写入 Dubbo attachment，便于后续电商 RPC 调用关联。
 */
@Activate(group = {CommonConstants.CONSUMER, CommonConstants.PROVIDER})
public class DubboTraceFilter implements Filter {

    /**
     * 传递 Trace ID。
     *
     * @param invoker    调用器
     * @param invocation 调用
     * @return 结果
     */
    @Override
    public Result invoke(Invoker<?> invoker, Invocation invocation) throws RpcException {
        String traceId = MDC.get(TraceConstants.MDC_TRACE_ID);
        if (traceId != null) {
            RpcContext.getClientAttachment().setAttachment(TraceConstants.MDC_TRACE_ID, traceId);
            invocation.setAttachment(TraceConstants.MDC_TRACE_ID, traceId);
        }
        String incoming = invocation.getAttachment(TraceConstants.MDC_TRACE_ID);
        if (incoming != null && MDC.get(TraceConstants.MDC_TRACE_ID) == null) {
            MDC.put(TraceConstants.MDC_TRACE_ID, incoming);
        }
        return invoker.invoke(invocation);
    }
}
