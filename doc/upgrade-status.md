# 升级实施记录

更新：2026-11-03。代码基线 c29743a，开发分支 refine。

## 范围与顺序

PR-01 版本化契约与迁移 → PR-02 数据/运行隔离与持久作业 → PR-03 领域 MCP 和运行时扩展 → PR-04 搜索供应商单选。
后续 M2b 标注、M3 按需采集、M4 证据论坛、M5 内容结构与工作台、M6 预测、M7 情景与多模态均未验收。
不修改外部论文工程；当前默认业务入口仍为兼容流程。

## 验证记录

- PR-01：新增测试先因缺少 opinion_core 失败；实现后契约/迁移/格式/Stage1 共 24 项通过。
  随后补充真实旧 fixture 的 topics 列表测试，先失败再修复。
- 本轮使用 uv 创建仓库内 .venv；没有付费调用或抓取。
- 标注门槛待确认，不能宣称 M0 科学评测已完成；节费 50%–70% 仍是待验证目标。

## PR-01 接口

见[契约与迁移](modules/opinion-contracts.md)。新业务在 opinion_core；旧节点仍消费历史字段，
belief network/publisher_decision 的全链路移除属于 M2b，不能仅通过新契约省略字段就视为已完成。

## PR-02 运行隔离

DatasetRepository 在服务根目录内使用 event/datasets/ds-SHA256.json，运行目录为 event/runs/dataset/run。
数据按内容版本隔离，无共享可变缓存；每次读取核验指纹。文件写入用同目录临时文件和原子替换。
路径拒绝越界 ID 和指向根外的链接。run_context 注入所有旧 MCP 显式输出路径；调用者须显式绑定，
旧 PocketFlow 环境变量模式仍要求独立子进程，不能在同进程并发切换。

JobStore 持久保存参数、幂等键、状态、修订号、租约和批次结果。状态变更必须传当前 revision；
终态不能复活，取消已接受后完成不能覆盖。Worker 可领取排队/租约过期任务，heartbeat 续约，
commit_batch 验证所有者、租约、运行状态并按 batch_id 幂等提交。API 费用不确定性仍需标注 Worker 接入时记录。
当前仅提供作业基础设施，未接付费标注/采集 Worker；不能宣称崩溃后外部请求恰好执行一次。

定向测试：13 项通过，包括不同事件并发目录、跨事件读取拒绝、数据版本、取消/完成竞争、
重启读回、批次归属，以及旧 PathManager/status/MCP 暴露回归。

## PR-03 最小领域接入

新增可运行的领域 MCP 与 Streamlit 上传概览页，复用旧 IR 渲染器。7 个工具提供注册、统计、
分页证据、短报告、产物读取、任务查询/取消。配置示例保留真实上游出处；无上游源码复制。
定向测试 19 项通过，包含真实 Windows stdio 子进程。报告输入/阶段前提测试先失败再实现。
全量测试暴露旧 Windows os.kill(pid,0) 探测导致中断，新增失败测试后修为 tasklist 精确 PID 读取。
上游 Agent Runtime/浏览器/真实模型验收仍未执行，M1 不标为完成。见[运行手册](modules/domain-gateway.md)。

## PR-04 搜索单选

统一 provider 接口和两个实际 HTTP adapter，旧 web_search 返回兼容投影，保留完整证据与响应。
配置和 Pipeline Console 支持二选一；不跨供应商回退，不新增禁用搜索模式。
46 项定向测试通过。Tavily 单次真实 smoke 因认证失败未通过；DeepSeek 无环境凭据，未调用。
PR-01 至 PR-03 的全量离线回归为 413 passed / 1 skipped / 4 deselected，4 个旧图表警告。
后续全量结果以本文件最后一次记录为准。详见[搜索接口](modules/search-providers.md)。
