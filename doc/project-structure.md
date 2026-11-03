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
├── K8S_QUICK_START.md                # K8s 模板使用说明
│
├── backend/                         # Python 后端，独立 UV 环境
│   ├── Makefile                     # 后端安装、Gateway、Worker、静态检查
│   ├── pyproject.toml               # 后端依赖与包定义
│   ├── uv.lock                      # 后端依赖锁
│   ├── langgraph.json               # LangGraph 图入口配置
│   ├── src/
│   │   ├── agents/                  # Agent Runtime 核心
│   │   │   ├── lead_agent/          # 工厂、提示词、图导出
│   │   │   ├── middlewares/         # 上下文、技能注入、请求范围校验
│   │   │   ├── memory/              # 会话消息、显式记忆、持久事件
│   │   │   ├── checkpointer/        # LangGraph SQLite 检查点
│   │   │   └── thread_state.py      # 图状态定义
│   │   ├── gateway/                 # FastAPI 应用层
│   │   │   ├── app.py               # 应用工厂与生命周期
│   │   │   ├── runtime.py           # Agent 执行、取消、事件发布
│   │   │   ├── dependencies.py      # 配置、线程仓库、Runtime 注入
│   │   │   └── routers/             # threads/runs/events/datasets/artifacts/system
│   │   ├── sandbox/                 # 线程文件区与路径约束
│   │   ├── subagents/               # 专业角色注册与受限执行
│   │   ├── tools/                   # 领域工具入口、CLI 与 Worker 启动
│   │   ├── mcp/                     # MCP 配置、发现和调用客户端
│   │   ├── models/                  # 模型工厂与 SDK 适配
│   │   ├── skills/                  # 项目技能加载
│   │   ├── config/                  # YAML/环境变量加载与类型化配置
│   │   └── domain/                  # 迁入的新旧可复用领域实现
│   │       ├── opinion_core/
│   │       │   ├── schemas/         # 事件、标签、请求、任务、产物契约
│   │       │   ├── ingestion/       # 历史数据无损迁移
│   │       │   ├── labeling/        # 事件 Schema、自动弱标注、词表
│   │       │   │   ├── sampling.py  # 高阅读量池随机抽样，仅用于标签发现
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
│   │       └── crawler_worker/      # 独立采集执行器、X 官方 API、连接器协议
│   └── tests/                       # 离线工程契约与 Worker 集成检查
│
├── frontend/                        # Next.js + React + TypeScript
│   ├── package.json
│   ├── package-lock.json
│   ├── next.config.ts               # standalone 构建与 API 代理
│   ├── tsconfig.json
│   └── src/
│       ├── app/                     # App Router、布局、工作区和聊天页
│       ├── components/              # 工作台、任务面板、产物查看器
│       │   ├── workflow-builder.tsx # 输入、阶段、角色、模型及本机凭据
│       │   ├── forum-view.tsx       # 讨论、补充行动、分歧与停止原因
│       │   ├── analysis-chart.tsx   # 交互图表、序列筛选和来源表
│       │   └── report-view.tsx      # 章节化报告与证据引用
│       ├── hooks/                   # SSE 事件流与游标续读
│       └── lib/                     # API 客户端和共享类型
│
├── skills/
│   ├── public/                      # 当前 3 个项目技能
│   │   ├── event-analysis/
│   │   ├── evidence-report/
│   │   └── forecast-scenario/
│   └── custom/                      # 本机自定义技能，gitignored
│
├── docker/
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   ├── docker-compose-dev.yaml      # Gateway/Worker/前端/Nginx
│   ├── docker-compose-production.yaml
│   ├── nginx/default.conf           # 同源路由与 SSE 代理
│   └── k8s/app.yaml                 # 单副本、共享卷、Secret 引用模板
│
├── scripts/                         # 本地启动/停止、静态检查及兼容启动器
├── doc/                             # 架构、目录、配置、部署和实施记录
├── tests/                           # 领域契约与历史模块测试
├── configs/                         # 领域请求等示例
├── main.py                          # 兼容领域 CLI
├── opinion_core/                    # 旧导入路径转发至 backend/src/domain
├── opinion_gateway/                 # 旧导入路径转发
├── crawler_worker/                  # 旧导入路径转发
├── agent_runtime_extension/         # 外部工具绑定兼容层，planner 转发
├── intelligent_ui/                  # 保留的 Streamlit 视图与 PDF 导出
├── legacy/                          # 原 PocketFlow 入口与本机旧配置
├── flow.py / nodes/ / dashboard/     # 历史模块，供显式兼容入口使用
├── pyproject.toml / uv.lock          # 保留的兼容环境
├── .app-state/                      # 运行生成：会话、检查点、进程日志
└── .opinion-assets/                  # 运行生成：数据、领域作业与版本资产
```

参见 [分层架构](architecture.md)、[Agent Runtime](modules/agent-runtime-architecture.md) 和 [复用清单](modules/architecture-rewrite.md)。
