# Domain Tool Service 运行手册

更新：2026-11-03。当前交付为 M1 的上传资料概览子链路，不是完整产品验收。

## 运行

在仓库根目录执行 `uv run python -m opinion_gateway.mcp_server --root .opinion-assets` 启动 stdio MCP。
`uv run streamlit run dashboard/app.py` 后进入 opinion_workbench 页面，可上传标准 PostRecord JSON。
示例输入：

```json
[{"post_id":"p1","raw_id":"1","platform":"test","content":"原始正文"}]
```

工具顺序：register_dataset(event_id, records) → describe_dataset(event_id,dataset_id,run_id)
→ read_evidence(相同引用,offset,limit) → render_report(相同引用) → read_artifact(artifact_id=report)。
注册只校验入库，不启动爬虫或调用模型。统计返回总数、时间有效数、平台计数；证据分页最大 100 条，
每条摘要最多 500 字。报告复用现有 Stage3 IR 渲染器，数值由程序写入，保留统计及帖子引用。
RunManifest、统计和报告存于对应运行目录。job_status/cancel_job 必须匹配 event_id。
仅 completed 的报告可读取，取消/失败时在途输出不作为正式产物发布。

## 权限与隔离

MCP 不接收任意文件路径；本地操作者在启动时设置资产根目录。event/dataset/run 引用都经过验证。
这是本机单用户服务，事件匹配校验不是多租户身份认证。启动时不要公开给不受信任的网络调用者。
不读取/推断缺失标签；未执行搜索的资料概览不宣称已经生成冻结事件 schema。

## Agent Runtime

配置与 Insight/Query 定义见 [agent_runtime_extension](../../agent_runtime_extension/README.md)。
上游参考固定在 `1dd6d056278536af1cb4fc60347f4ca40fcb629b`；样例核对了官方
[MCP 配置](https://github.com/bytedance/deer-flow/blob/1dd6d056278536af1cb4fc60347f4ca40fcb629b/extensions_config.example.json)
和 [custom_agents 注册](https://github.com/bytedance/deer-flow/blob/1dd6d056278536af1cb4fc60347f4ca40fcb629b/backend/packages/harness/deerflow/subagents/registry.py)。
角色白名单中的名称必须与实际运行时发现结果对应，样例无前缀名称不能直接冒充已经验证的运行时配置。

## 验证与限制

MCP 内存传输测试覆盖发现、输入拒绝、阶段前提、统计、证据、报告和跨事件作业访问。
另用真实 Python 子进程 stdio 在 Windows 验证工具发现与上传，未调用外部模型。
Windows 旧运行锁的 PID 检测已改用隐藏 tasklist，不向进程发送 signal。

尚未完成：上游 Agent Runtime 安装/浏览器/真实模型端到端验收、长任务调度 UI、刷新后运行选择、
完整 ContentBundle、外部证据论坛和新标签标注。当前 Streamlit 页面保存会话内引用；重启后可经 MCP
用已记录 event/dataset/run/job ID 读取持久资产。不要将本地协议测试称为真实 API 或浏览器 E2E。
