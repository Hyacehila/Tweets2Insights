# 本地事件 Demo 数据集

更新：2026-11-04

先用 300 条河南夜骑开封图文帖子体验完整复盘，再运行较大数据集。准备与导入不调用模型；在工作台点击“开始执行”后才进入标注、分析论坛和报告生成。

## 数据版本

| 数据集 | 帖子上限 | 输入方式 |
|---|---:|---|
| 河南图文成本试用 | 300 | 从带可用配图的帖子中选取，每帖最多输入 3 张 |
| 河南正式文本 Demo | 10,000 | 仅文字 |
| 河南正式图文 Demo | 10,000 | 与文本版相同帖子，有配图时联合输入，每帖最多 3 张 |
| 北京暴雨文本 Demo | 10,000 | 现有 Excel 的文字数据 |

北京源表没有配图列、嵌入图片或配套图片文件；补充图片来源后可另建图文版。河南使用 `posts.cleaned.json`，不合并同目录的 JSON、CSV、Excel 副本。

## 筛选规则

- 以北京时间自然日划分窗口。两个来源没有阅读量，热度采用点赞数、评论数、转发数之和。
- 当名额足够覆盖全部日期时，每天先分配 1 条，其余按当天剩余帖子数分配，最大余数法补足总数。每天取热度最高的帖子，同分按发布时间和稳定 ID 排序。
- 有效记录不足上限时全部保留。300 条图文试用只从带可用图片的记录中筛选；正式图文版保留无图帖子，与正式文本版保持同一帖子集合。
- 北京原帖链接去掉查询参数后去重，同一原帖保留互动量最高的记录。不能确定时间的记录和无正文无配图的记录列入排除清单。“赞／评论／转发”等按钮文字保留为缺失数值，排序时贡献 0，不冒充观测到的 0 次互动。
- 河南没有完整的原帖 ID，保留清洗文件的源记录，不仅凭相同文字推断为重复。生成 ID 带源行号，方便回查。
- 图片按实际文件格式校验。GIF 转为第一帧，超大图片生成缩小的 JPEG 副本；原文件不变。损坏图片列入清单，300 条试用在可用候选中补足名额。单帖多余图片保存在数据集中，运行时按上限选择。

这些样本偏向高互动帖子，报告描述选取的样本，不代表全平台舆情比例。

## 整理命令

在项目根目录执行：

```powershell
uv run --project backend python scripts/prepare_event_demo.py --source "D:\Research\TRASER\Data\Events\henan\clean_data\posts.cleaned.json" --source-kind henan --event henan-vision-cost-300 --output data/demos/henan-vision-cost-300 --limit 300 --media-mode text_image --images-only --max-images-per-post 3
```

正式河南图文版移除 `--images-only`，将 `--limit` 设为 `10000`，并改用独立的事件 ID 与输出目录；文本版使用 `--media-mode text_only`。北京使用 `--source-kind beijingstorm` 和对应 Excel 路径。

脚本登记本地数据集和图片，生成 `posts.json`、`run.json`、`plan.json`、`manifest.json`、`daily-selection.json` 和 `source-map.json`。数据与图片资产保存在本机忽略目录。`posts.json` 中的 `dataset-image:` 引用属于登记的事件，换电脑或事件时需重新运行整理命令。

运行配置包含 1 个复盘目标、OpenAI Decisions 标注、默认论坛角色及三个报告 Agent。标注调用上限等于帖子数，总调用上限另外留出 64 次供标签体系、搜索、论坛和报告使用。仅编译计划不会提交任务。

## 运行与查看用量

1. 在工作台打开“河南夜骑开封 · 300 条图文成本试用”。
2. 查看已载入的高级运行配置，确认 300 次标注上限、图文模式和每帖 3 张。
3. 点击“开始执行”。Agent 模型沿用本机 API 设置，决策模型使用独立的 OpenAI 凭据。
4. 任务结束后，在“分析与报告”查看“用量与费用”：按阶段展示调用次数、输入／输出 Token、缓存 Token，以及未返回 Token 的调用数量。

用量来自供应商响应。没有返回金额时，页面显示费用未知，可用 Token 记录和服务商账单核对。论坛、搜索与报告也有消耗，比较文本和图文版本时应分别查看标注阶段与总用量。

## 自动检查

`backend/tests/test_demo_preparation.py` 覆盖时间与热度映射、逐日名额、全量阈值、去重、格式转换、损坏图片补选、数据登记和计划编译；`frontend/tests/usage-summary.test.mjs` 检查两种 Token 字段格式及未知费用显示。

```powershell
uv run --project backend pytest backend/tests/test_demo_preparation.py -q
npm --prefix frontend test
```
