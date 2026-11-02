# 爆品分析报表（LLM HTML + 前端下载）

## 做什么

代码打分、质检挂标、规则作战桶之后：

1. 锁定候选 JSON + `required_charts` 交给大模型生成 **完整 HTML**（Chart.js）  
2. 无 Key / 失败则 Chart.js 模板降级  
3. `upsert` 报告到 Java；响应带 **`download`** 给前端

正式分只来自 `scoring/`。

## 给前端

```json
{
  "download": {
    "available": true,
    "url": "/internal/dev/reports/{task_id}",
    "method": "GET",
    "filename": "explosion-report-{task_id}.html",
    "content_type": "text/html; charset=utf-8",
    "hint": "展示下载按钮"
  }
}
```

正式环境由 Java 把 Worker `result_meta.download.url` 换成网关对外路径。

## 联调

见 [internal-api-contract.md](internal-api-contract.md) §2.2。

