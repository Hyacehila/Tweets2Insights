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
- 标注门槛与规模已按用户补充限定于 Demo 验证，见[弱标注 Demo 协议](testing/weak-label-demo-protocol.md)；尚无真实评测结果，节费 50%–70% 仍是待验证目标。

## PR-01 接口

见[契约与迁移](modules/opinion-contracts.md)。新业务在 opinion_core；旧节点仍消费历史字段，
belief network/publisher_decision 的全链路移除属于 M2b，不能仅通过新契约省略字段就视为已完成。

## PR-02 运行隔离

DatasetRepository 在服务根目录内使用 SHA256(event)/datasets/ds-SHA256.json，运行目录为 SHA256(event)/runs/dataset/SHA256(run)。
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

## 第一轮边界修复

新增回归发现并修复 Windows 文件系统大小写串事件问题：目录键改为原始 ID 的 SHA256，逻辑 ID 保留原值。
新增取消发生在渲染期间的回归：取消请求最终落为 cancelled，未完成报告拒绝发布。
RunManifest.code_version 改为 opinion_core/opinion_gateway 与渲染源码指纹，不使用功能名称冒充代码版本。
真实 stdio 短报告初次超时，定位到旧 nodes 包引入 NumPy；将既有纯 IR 渲染函数抽至
opinion_core/reporting/ir_markdown.py，由新旧入口共用。完整 stdio 链路和定向回归共 10 项通过。

## 最终验证快照（2026-11-03）

`uv run pytest tests dashboard/tests -v`：425 passed、1 skipped、5 deselected、4 warnings（21.38 秒）。
完整日志保留在本地 `.opinion-assets/validation/offline.txt`（运行资产，不入 Git）。
默认跳过 live_api/ui_e2e；真实 stdio 上传→统计→证据→短报告集成已通过。
Tavily live 单查询返回 authentication；DeepSeek 未配置凭据。没有真实浏览器或上游 Agent Runtime 验收结论。
4 个警告来自既有图表刻度/相同坐标范围，未影响断言。

## 下一批实施与前置条件

1. M0：Demo 协议已登记 600 条（校准 200／独立测试 400）、逐字段 macro-F1 ≥ 0.80、覆盖率 ≥ 85%、相对同标签基线下降 ≤ 0.03；下一步准备 Demo 样本及评测入口。正式运行不进行人工标注验证。
2. M1：运行时工具前缀绑定、上游固定版本环境验证、实际标注/采集 Worker 接入仍待完成（资料概览 Worker 与刷新恢复 UI 已落实）。
3. M2a：修复本机 Tavily 凭据并配置 DeepSeek 环境密钥后，各执行一次小规模真实 smoke；无需重新跑付费大链路。
4. M2b：成功先导搜索→冻结词库/target→字段级标注与拒判，再迁移所有旧字段消费者和标签 UI。
5. M3–M7 尚未开始正式实现或科学验收。当前基础提交不表示整个升级或第一层产品已完成。

## 用户补充：人工验证仅用于 Demo（2026-11-03）

正式数据经模型弱标注后自动进入分析，不设逐批／逐事件人工复核。人工金标准只用于 Demo，
验证 Jev 或其他决策模型是否达到上述规模与质量门槛。保留自动契约校验、字段级拒判和失败处理。
此项更新明确工程边界，不代表 Demo 评测已经通过；不再把人工验证资源作为日常运行前置条件。


## 第二轮：持久 Worker 与工作台恢复

M1 新增独立 inventory Worker、排队提交、原子发布、租约令牌、断点恢复与幂等重试；
工作台支持新会话重连、任务列表、取消重试、产物下载。修复读取不存在报告会创建任务的副作用。
旧同步工具保留，异步链路的正式结果以 SQLite 中完成状态与结果的事务提交为准。
新增 7 项集成/AppTest 用例；既有租约检查点调用改为必须携带领取令牌。详见领域运行手册。

第二轮 Worker/UI 全量离线回归：432 passed、1 skipped、5 deselected，4 个既有图表警告。
