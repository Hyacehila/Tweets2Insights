# 资料概览 MCP 与兼容 Worker

本页介绍上传数据的资料概览接口与 InventoryWorker。完整研究流程和 19 个领域 MCP 工具见[运行手册](domain-application.md)。

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
服务面向本机单用户，网络访问要求见[安全说明](../../SECURITY.md)。
资料概览直接读取原始字段，事件 schema 由完整工作流中的准备阶段生成。

## Agent Runtime

配置与 Insight/Query 定义见 [agent_runtime_extension](../../agent_runtime_extension/README.md)。
上游参考固定在 `1dd6d056278536af1cb4fc60347f4ca40fcb629b`；样例核对了官方
[MCP 配置](https://github.com/bytedance/deer-flow/blob/1dd6d056278536af1cb4fc60347f4ca40fcb629b/extensions_config.example.json)
和 [custom_agents 注册](https://github.com/bytedance/deer-flow/blob/1dd6d056278536af1cb4fc60347f4ca40fcb629b/backend/packages/harness/deerflow/subagents/registry.py)。
角色白名单使用运行时发现的完整工具名，包含实际服务前缀。

## 测试与存储

MCP 内存传输测试覆盖发现、输入拒绝、阶段前提、统计、证据、报告和跨事件作业访问。
另用真实 Python 子进程 stdio 在 Windows 验证发现、上传、统计、证据、短报告和产物读取，未调用外部模型。
Windows 旧运行锁的 PID 检测已改用隐藏 tasklist，不向进程发送 signal。

自动标注、外部证据论坛和报告生成由 DomainWorker 执行，见[完整工作流](full-workflow.md)。
兼容工作台按事件读取持久任务，URL 保留所选任务，支持新会话重连。

物理目录使用 SHA256(event_id)/runs/dataset_id/SHA256(run_id)，避免 Windows 大小写与保留名称冲突。RunManifest 记录领域源码 SHA256。


## 持久任务执行与恢复

推荐工作台使用 register_dataset → submit_inventory_job → list_jobs/job_status → read_job_artifact。
submit_inventory_job 仅校验引用并入队，立即返回 JobRef，不在 Web 请求里生成报告。
另开终端在同一仓库执行：

```powershell
uv run python -m opinion_gateway.worker --root .opinion-assets
# 只处理一项可领取任务，适合 smoke / 外部调度
uv run python -m opinion_gateway.worker --root .opinion-assets --once
```

InventoryWorker 只领取 inventory_report 任务。
它依次提交 statistics、evidence 检查点，再将短报告与 completed 状态在同一 SQLite 事务中发布。
心跳续约；租约过期后可接管。每次领取产生唯一 lease_token，即使进程名称重复也不能提交旧租约结果。
取消优先阻止新阶段提交；Worker 死亡后的 cancel_requested 在租约到期时收敛为 cancelled。
retry_job 为停止任务建立一个幂等后继，保留原终态与已提交阶段。输入数据和代码版本不变时可复用。
代码变更后旧版本任务会失败，需重新提交当前代码版本任务，不能将不同代码版本的阶段混合。

工作台提供事件内任务列表、刷新、取消、重试、Markdown/运行证据下载。新会话不依赖原 session_state。
旧 render_report 同步工具保留兼容；read_artifact 已改为纯查询，不再因读取不存在报告而创建作业。
异步概览接口包括 submit_inventory_job、list_jobs、retry_job、read_job_artifact；完整工具目录见[运行手册](domain-application.md)。

验证：真实独立 Worker 子进程、租约接管/旧令牌拒绝、检查点恢复、取消/重试、读操作无副作用，
以及 Streamlit AppTest 新会话重连与取消重试。
