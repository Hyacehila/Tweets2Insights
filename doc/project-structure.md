# 项目目录

```text
Tweets2Insights/
├── Makefile                         # install / dev / stop / check / test
├── config.yaml                      # 主应用配置，不保存密钥
├── config.example.yaml              # 主配置模板
├── extensions_config.json           # MCP 服务和技能启用配置
├── .env                             # 本机密钥与连接器变量，gitignored
├── .env.example                     # 空密钥环境模板
├── .provider-secrets.json           # UI 保存的本机凭据，gitignored
├── README.md                        # 默认启动方法和项目说明
├── CONTRIBUTING.md                  # 分层约束与开发指南
├── SECURITY.md                      # 当前安全边界
│
├── backend/                         # Python 后端，独立 UV 环境
│   ├── Makefile                     # 后端安装、Gateway、Worker、静态检查
│   ├── pyproject.toml               # 后端依赖与包定义
│   ├── uv.lock                      # 后端依赖锁
│   ├── src/
│   │   ├── agents/                  # Agent Runtime 核心
│   │   │   ├── lead_agent/          # 工厂、提示词与编排
│   │   │   ├── middlewares/         # 上下文、技能注入、请求范围校验
│   │   │   ├── memory/              # 会话消息、显式记忆、持久事件
│   │   │   ├── checkpointer/        # LangGraph SQLite 检查点
│   │   │   └── thread_state.py      # 图状态定义
│   │   ├── gateway/                 # FastAPI 应用层
│   │   │   ├── app.py               # 应用工厂与生命周期
│   │   │   ├── runtime.py           # Agent 执行、取消、事件发布
│   │   │   ├── event_deletion.py    # 删除事件研究记录与产物，保留数据集
│   │   │   ├── dependencies.py      # 配置、线程仓库、Runtime 注入
│   │   │   └── routers/             # threads/runs/events/datasets/artifacts/system
│   │   ├── subagents/               # 专业角色注册与受限执行
│   │   ├── tools/                   # 领域工具入口、CLI 与 Worker 启动
│   │   ├── mcp/                     # MCP 配置、发现和调用客户端
│   │   ├── models/                  # 通用 OpenAI 兼容 Agent 模型工厂
│   │   ├── skills/                  # 项目技能加载
│   │   ├── config/                  # YAML/环境变量加载与类型化配置
│   │   └── domain/                  # 迁入的新旧可复用领域实现
│   │       ├── opinion_core/
│   │       │   ├── schemas/         # 事件、标签、请求、任务、产物契约
│   │       │   │   └── agent_model.py # 模型接口与生成参数契约
│   │       │   ├── ingestion/       # 历史数据迁移、Demo 字段映射与逐日热度筛选
│   │       │   ├── labeling/        # 事件 Schema、自动弱标注、词表
│   │       │   │   ├── sampling.py  # 高阅读量池随机抽样，仅用于标签发现
│   │       │   │   ├── openai_provider.py # 通用 Chat Completions JSON 适配
│   │       │   │   ├── openai_decisions.py # OpenAI 原生决策标注与类别概率
│   │       │   │   ├── media.py     # 模型图片能力、每帖上限、图像预处理与内容指纹
│   │       │   │   ├── schema_builder.py # 通用 Agent 标签体系设计
│   │       │   │   └── system_one.py # Jev / 阿里 decision 原生协议
│   │       │   ├── evidence/        # 搜索适配、证据卡、论坛、多模态接口
│   │       │   ├── analytics/       # 分布观测、图表、复用 NLP
│   │       │   │   └── toolbox.py   # 41 个工具入口、参数、来源表及图表
│   │       │   ├── dynamics/        # 联合 HK、同化、预测与回测
│   │       │   │   └── latent.py    # PCA 编解码与训练内滚动参数选择
│   │       │   ├── scenarios/       # 配对条件情景
│   │       │   ├── reporting/       # 内容、结构、引用校验与渲染
│   │       │   │   └── agents.py    # 内容整理 / 社科解释 / 页面布局
│   │       │   ├── evaluation/      # Demo 与消融脚本，后置评测
│   │       │   └── orchestration.py # 确定性领域计划编译
│   │       ├── opinion_gateway/     # MCP 服务、应用服务、资产、预算、Job/Worker
│   │       │   ├── supervisor.py    # 实时监控、角色状态与错误诊断 Agent
│   │       │   ├── diagnostics.py   # 异常正文、调用栈与凭据脱敏
│   │       │   ├── workspace_views.py # 概览统计、运行进度与用量接口
│   │       │   ├── media_assets.py  # 数据集配图原文件存储与事件隔离
│   │       │   ├── demo_preparation.py # 本地 Demo 图片整理、登记与运行配置
│   │       │   ├── agent_models.py  # 推荐模型、配置保存与端点凭据解析
│   │       │   └── label_providers.py # Worker/CLI 共用决策标注适配器
│   │       └── crawler_worker/      # MediaCrawler 隔离执行、平台适配、配图与限额
│   └── tests/                       # 离线工程契约与 Worker 集成检查
│
├── frontend/                        # Next.js + React + Tremor + TypeScript
│   ├── package.json
│   ├── package-lock.json
│   ├── postcss.config.mjs           # Tailwind CSS 构建
│   ├── TREMOR_LICENSE               # 复用组件的 MIT 许可
│   ├── next.config.ts               # 本机 API 代理
│   ├── tsconfig.json
│   ├── public/images/               # 启动页信息传播背景
│   ├── tests/                       # 界面语言转换检查
│   └── src/
│       ├── app/                     # App Router、布局、工作区和聊天页
│       ├── components/              # 工作台、任务面板、产物查看器
│       │   ├── launch-page.tsx      # 独立启动页
│       │   ├── research-dashboard.tsx # 分析看板与数据统计
│       │   ├── research-progress.tsx # 监控汇报、Agent 状态、日志与错误分析
│       │   ├── report-library.tsx   # 最终分析报告
│       │   ├── crawler-settings.tsx # MediaCrawler 平台登录
│       │   ├── workflow-builder.tsx # 输入、阶段、角色和模型参数
│       │   ├── recent-research.tsx  # 最近研究、重命名、右键删除
│       │   ├── tremor/              # Tremor Card / Badge
│       │   ├── provider-settings.tsx # 独立 API 设置页
│       │   ├── agent-model-settings.tsx # 模型推荐、参数与兼容性检测
│       │   ├── language-provider.tsx # 中英文切换与本机语言记忆
│       │   ├── specialty-chart.tsx   # 热图、网络与词云
│       │   ├── forum-view.tsx       # 讨论、补充行动、分歧与停止原因
│       │   ├── analysis-chart.tsx   # 交互图表、序列筛选和来源表
│       │   └── report-view.tsx      # 章节化报告与证据引用
│       ├── hooks/                   # SSE 事件流与游标续读
│       └── lib/                     # API 客户端、共享类型和中英文文案
│
├── skills/
│   ├── public/                      # 当前 3 个项目技能
│   │   ├── event-analysis/
│   │   ├── evidence-report/
│   │   └── forecast-scenario/
│   └── custom/                      # 本机自定义技能，gitignored
│
├── scripts/                         # 本地启动/停止、Demo 整理、静态检查及兼容启动器
├── doc/                             # 架构、目录、配置与部署说明
│   └── diagrams/                    # 系统、论坛、预测情景图及 Mermaid 源文件
├── tests/                           # 领域契约与历史模块测试
├── configs/                         # 领域请求等示例
├── data/                            # 输入数据与兼容词库
│   └── publisher_objects.json        # 7 类基础发布者类型
├── main.py                          # 兼容领域 CLI
├── opinion_core/                    # 旧导入路径转发至 backend/src/domain
├── opinion_gateway/                 # 旧导入路径转发
├── crawler_worker/                  # 旧导入路径转发
├── intelligent_ui/                  # 保留的 Streamlit 视图与 PDF 导出
├── legacy/                          # 原 PocketFlow 入口与本机旧配置
├── flow.py / nodes/ / dashboard/     # 历史模块，供显式兼容入口使用
├── pyproject.toml / uv.lock          # 保留的兼容环境
├── .app-state/                      # 运行生成：会话、检查点、进程日志
└── .opinion-assets/                  # 运行生成：数据、领域作业与版本资产
```

参见 [分层架构](architecture.md)、[Agent Runtime](modules/agent-runtime-architecture.md) 和 [复用清单](modules/architecture-rewrite.md)。
