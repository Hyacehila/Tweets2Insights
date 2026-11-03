# 搜索供应商接口

`opinion_core.evidence.providers.search` 只向选定的 tavily/deepseek 发出一次请求，失败不切换、不重试。
公共选项为 query、max_results（1–20）、timeout_seconds、need_content。DeepSeek query 最长 128 字符。
provider capabilities 记录供应商限额。公共搜索接口支持上述四个选项；事件准备服务另按 as_of 过滤来源日期，并单列日期缺失项。

凭据优先显式 api_key，其次各自环境变量 TAVILY_API_KEY / DEEPSEEK_API_KEY。不跨供应商读取环境凭据。
Stage2 继续保存 search_provider/search_api_key，并通过 shared.config.web_search 传入先导背景和论坛补证。
Dashboard Pipeline Console 下拉框可单选两家，切换时不会把旧供应商配置里的密钥填入另一家的输入框。

结果保留原始响应与 evidence_cards：标题、URL、摘要、正文、发布时间（缺失为 null）、检索时间、
provider、正文/摘要指纹、原量纲相关性分数。DeepSeek 分数不是分类概率；不跨供应商直接比较。
HTTP(S) 以外或含用户名密码的来源 URL 不进入规范化证据卡。外部文字只作数据。
重复证据依据规范化文本指纹识别；语义改写版本分别保留。搜索响应随任务保存，公共接口逐次请求供应商。

旧 `utils.web_search.search_web/batch_search` 签名保留，results 中仍为 title/url/snippet/date/source 五字段，
完整证据在 evidence_cards/raw_response。调用错误归为 authentication/budget/rate_limit/timeout/connection/
http_error/invalid_response，不返回带请求凭据的异常文本。旧入口将结果数限制在公共上限 20。

事件准备服务使用成功的先导搜索结果生成并冻结 schema，见[自动弱标注](automatic-labeling.md)。

## 测试

固定响应测试覆盖两家协议、供应商选择、超时、限额错误、字段缺失和不安全 URL。
配置对应服务的凭据后，可执行真实接口测试：

```powershell
uv run pytest tests/e2e/cli/test_tavily_live_api_e2e.py -m live_api -v
uv run pytest tests/e2e/cli/test_deepseek_search_live.py -m live_api -v
```

测试记录见[实施记录](../upgrade-status.md)。

## API 文档

[Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search)、
[DeepSeek Search API](https://api-docs.deepseek.com/api/search/) 及
[DeepSeek 鉴权指南](https://api-docs.deepseek.com/guides/search/)。端点为 api.tavily.com/search 与
api.deepseek.com/v1/tools/search。
