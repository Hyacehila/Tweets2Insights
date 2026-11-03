# 搜索供应商接口

更新：2026-11-03。PR-04。

`opinion_core.evidence.providers.search` 只向选定的 tavily/deepseek 发出一次请求，失败不切换、不重试。
公共选项为 query、max_results（1–20）、timeout_seconds、need_content。DeepSeek query 最长 128 字符。
provider capabilities 记录供应商限额；日期过滤尚未在公共接口暴露，不能声称历史搜索无未来泄漏。

凭据优先显式 api_key，其次各自环境变量 TAVILY_API_KEY / DEEPSEEK_API_KEY。不跨供应商读取环境凭据。
Stage2 继续保存 search_provider/search_api_key，并通过 shared.config.web_search 传入先导背景和论坛补证。
Dashboard Pipeline Console 下拉框可单选两家，切换时不会把旧供应商配置里的密钥填入另一家的输入框。

结果保留原始响应与 evidence_cards：标题、URL、摘要、正文、发布时间（缺失为 null）、检索时间、
provider、正文/摘要指纹、原量纲相关性分数。DeepSeek 分数不是分类概率；不跨供应商直接比较。
HTTP(S) 以外或含用户名密码的来源 URL 不进入规范化证据卡。外部文字只作数据。
相同规范化文本得到相同指纹，可用于识别重复证据，但当前尚未实现转载语义去重或持久搜索缓存。

旧 `utils.web_search.search_web/batch_search` 签名保留，results 中仍为 title/url/snippet/date/source 五字段，
完整证据在 evidence_cards/raw_response。调用错误归为 authentication/budget/rate_limit/timeout/connection/
http_error/invalid_response，不返回带请求凭据的异常文本。旧入口将结果数限制在公共上限 20。

新事件冻结 schema 和成功先导搜索的服务端门禁属于 M2b；本提交不生成 schema，也不新增跳过搜索模式。

## 验证

46 项适配器、旧搜索、配置与 Dashboard API 定向测试通过。固定响应测试覆盖两家协议、只调用所选服务、
超时、限额错误、字段缺失和不安全 URL。2026-11-03 Tavily 单查询 live smoke 返回 authentication，
未通过真实验收；DeepSeek 环境凭据缺失，未运行真实调用。可分别显式执行：

```powershell
uv run pytest tests/e2e/cli/test_tavily_live_api_e2e.py -m live_api -v
uv run pytest tests/e2e/cli/test_deepseek_search_live.py -m live_api -v
```

## 官方依据

本轮核对 [Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search)、
[DeepSeek Search API](https://api-docs.deepseek.com/api/search/) 及
[DeepSeek 鉴权指南](https://api-docs.deepseek.com/guides/search/)。端点为 api.tavily.com/search 与
api.deepseek.com/v1/tools/search；参考文档不代表真实凭据可用。
