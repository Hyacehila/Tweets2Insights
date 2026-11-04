# 阶段 1：数据增强子系统

> **文档状态**: 2026-11-04 更新
> **关联源码**: `nodes/stage1/*`, `nodes/base.py`, `flow.py`  
> **上级文档**: [系统设计总览](design.md)

---

## 1. 概述

### 1.1 目标

将非结构化的社交媒体博文转化为**五维结构化数据**，为后续的统计分析和报告生成提供标准化输入。

### 1.2 输入/输出

| 项目 | 说明 |
|:---|:---|
| **输入** | `data/posts_sample_30.json` — 原始博文 JSON 数组（可配置） |
| **输出** | `data/enhanced_posts_sample_30.json` — 增强后的博文 JSON 数组（可配置） |
| **参考数据** | `data/topics.json`、`data/sentiment_attributes.json`、`data/publisher_objects.json`、`data/believe_system_common.json` |

### 1.3 执行模式

阶段 1 采用异步并行模式（`enhancement_mode = "async"`）：通过 `AsyncFlow` 直接调用 LLM API，支持并发控制与 Checkpoint。并发上限由 `runtime.concurrent_num` 统一配置。

---

## 2. 五个增强维度

每条博文经过阶段 1 处理后，会新增以下 5 个字段：

### 2.1 维度定义

| # | 字段名 | 类型 | 说明 | 取值/示例 |
|:---|:---|:---|:---|:---|
| 1 | `sentiment_polarity` | `int` | 情感极性评分 | 1=极度悲观, 2=悲观, 3=中性, 4=乐观, 5=极度乐观 |
| 2 | `sentiment_attribute` | `List[str]` | 情感属性标签（1-3 个） | `["支持", "期待"]` |
| 3 | `topics` | `List[Dict]` | 二级主题分类（1-2 个） | `[{"parent_topic": "灾害", "sub_topic": "暴雨"}]` |
| 4 | `publisher` | `str` | 发布者类型 | `"新闻媒体"` / `"个人用户"` |
| 5 | `belief_signals` | `List[Dict]` | 信念体系信号（1-3 个） | `[{"category": "安全", "subcategories": ["人身安全"]}]` |

发布者词库统一为政府机构、新闻媒体、自媒体、企业账号、事业单位、社会组织、个人用户，分类边界见[基础类型说明](automatic-labeling.md#发布者基础类型)。

### 2.2 参考数据来源

各维度的候选值列表来自 `data/` 目录下的 JSON 文件，在 `DataLoadNode` 中加载：

| 维度 | 参考数据文件 | 加载到 `shared` 的键 |
|:---|:---|:---|
| sentiment_attribute | `data/sentiment_attributes.json` | `data.sentiment_attributes` |
| topics | `data/topics.json` | `data.topics_hierarchy` |
| publisher | `data/publisher_objects.json` | `data.publisher_objects` |
| belief_signals | `data/believe_system_common.json` | `data.belief_system` |

> `sentiment_polarity` 维度不需要参考数据，直接由 LLM 输出 1-5 的数字。

### 2.3 NLP 增强字段（新增）

阶段 1 在五维增强前增加 **NLPEnrichmentNode**，对文本进行本地处理，新增字段：

| 字段名 | 类型 | 说明 |
|:---|:---|:---|
| `keywords` | `List[str]` | 关键词列表（Top-N） |
| `entities` | `List[str]` | 轻量命名实体（#话题#、@用户 等规则） |
| `lexicon_sentiment` | `Dict` | 词典情感（label/score/pos/neg） |
| `text_similarity_group` | `int` | 文本相似聚类编号（无聚类记为 -1） |

---

## 3. 异步并行模式 (Async)

### 3.1 Flow 节点链路

```mermaid
flowchart LR
    DL[DataLoadNode] --> NE[NLPEnrichment]
    NE --> SP[SentimentPolarity]
    SP --> SA[SentimentAttribute]
    SA --> TP[TopicAnalysis]
    TP --> PO[PublisherObject]
    PO --> BS[BeliefSystem]
    BS --> SD[SaveEnhancedData]
    SD --> DV[DataValidation]
    DV --> SC[Stage1Completion]
```

5 个分析节点**串行执行**（非并行），每个节点内部对所有博文进行**异步并发**处理。

### 3.2 `AsyncParallelBatchNode` 基类

所有 5 个分析节点都继承自 `AsyncParallelBatchNode`，该类组合了 PocketFlow 的 `AsyncNode` 和 `BatchNode`。

#### 核心特性

| 特性 | 实现方式 |
|:---|:---|
| **并发控制** | 构造时传入 `max_concurrent`，来源为 `runtime.concurrent_num`（默认 60），内部使用 worker 数量限制（`max_workers = max_concurrent or min(200, total)`） |
| **断点续传** | Checkpoint 机制：每完成 N 条自动保存到增强数据文件 |
| **错误处理** | 子类可实现 `exec_fallback_async` 提供降级返回值 |
| **增量写回** | 子类实现 `apply_item_result` 将单条结果立即写回原博文对象 |

#### 并发执行模型

```
┌─────────────────────────────────────────────────┐
│  _exec(items)                                   │
│                                                 │
│  index_queue ──→ Worker 1 ──→ done_queue        │
│           ╲──→ Worker 2 ──→──╲                  │
│            ╲──→ Worker 3 ──→──╲                 │
│             ...                ↓                │
│                          Aggregator             │
│                    (apply_item_result            │
│                     + checkpoint_save)           │
└─────────────────────────────────────────────────┘
```

- **Worker 队列模式**：使用 `asyncio.Queue` 分发索引，`max_workers` 个 worker 并发消费
- **Aggregator**：汇集所有结果，每条结果完成后调用 `apply_item_result` 写回原数据，并按配置触发 Checkpoint 保存

#### Checkpoint 机制

通过 `_configure_checkpoint(shared, blog_data_ref)` 配置，从 `shared["config"]["stage1_checkpoint"]` 读取：

| 配置项 | 默认值 | 说明 |
|:---|:---|:---|
| `enabled` | `True` | 是否启用 |
| `save_every` | `200` | 每完成 N 条保存一次（设为 1 即每条都保存） |
| `min_interval_seconds` | `20` | 最小保存间隔（秒），防止频繁写盘 |
| `output_path` | 来自 `config.data_source.enhanced_data_path` | 保存路径 |

**保存逻辑**：
1. Aggregator 每收到一条结果，计数器 +1
2. 当 `completed % save_every == 0` 时，尝试保存
3. 保存前检查距上次保存是否超过 `min_interval_seconds`
4. 使用 `asyncio.Lock` 保证并发安全
5. 所有条目处理完毕后强制保存一次（`force=True`）
6. 实际保存通过 `asyncio.to_thread(save_enhanced_blog_data, ...)` 在线程池中执行

### 3.3 六个分析节点详解

所有分析节点共享相同的三阶段生命周期模式：

```
prep_async(shared)  → 返回 items 列表
exec_async(item)    → 对单条 item 调用 LLM，返回结果
post_async(shared, prep_res, exec_res) → 将结果批量写回 shared
```

#### 3.3.1 `AsyncSentimentPolarityAnalysisBatchNode`

| 属性 | 值 |
|:---|:---|
| **输出字段** | `sentiment_polarity` (int: 1-5) |
| **LLM 模型** | 有图片：`call_glm4v_plus`；纯文本：`call_glm_45_air` |
| **Temperature** | 0.3 |
| **Fallback** | 返回 3（中性） |

**Prompt 策略**：
- 指令明确要求只输出一个数字（0-5），不附加解释
- 支持多模态：如果博文含图片，使用视觉模型
- 响应解析：`strip()` → `isdigit()` 验证 → 范围检查 `1 ≤ score ≤ 5`

**跳过逻辑**：如果 `blog_post.get("sentiment_polarity")` 已有值，直接返回（支持断点续传）

**图片处理**：
- 从 `image_urls` 字段读取图片路径列表
- 非绝对路径会自动加上 `data/` 前缀

#### 3.3.2 `AsyncSentimentAttributeAnalysisBatchNode`

| 属性 | 值 |
|:---|:---|
| **输出字段** | `sentiment_attribute` (List[str]) |
| **LLM 模型** | `call_glm_45_air`（纯文本） |
| **Temperature** | 0.3 |
| **Fallback** | `["中立"]` |

**Prompt 策略**：
- 将候选情感属性用顿号连接传入 Prompt
- 要求输出 JSON 数组格式
- 响应解析：`json.loads()` → 类型验证 → 过滤有效属性（必须在候选列表中）

**数据打包**：`prep_async` 将每条博文和 `sentiment_attributes` 列表组合成 `{"blog_data": ..., "sentiment_attributes": ...}` 传给 `exec_async`

**`apply_item_result` 实现**：访问 `item["blog_data"]["sentiment_attribute"]` 写回

#### 3.3.3 `AsyncTwoLevelTopicAnalysisBatchNode`

| 属性 | 值 |
|:---|:---|
| **输出字段** | `topics` (List[Dict]) |
| **LLM 模型** | 有图片：`call_glm4v_plus`；纯文本：`call_glm_45_air` |
| **Temperature** | 0.3 |
| **Fallback** | `[]`（空列表） |

**Prompt 策略**：
- 将主题层次结构展开为 `"父主题 -> 子主题1、子主题2"` 格式
- 要求输出 `[{"parent_topic": "...", "sub_topic": "..."}]` JSON 数组
- 支持多模态（与情感极性相同的图片处理逻辑）

**验证逻辑**：双重验证
1. `parent_topic` 必须在 `topics_hierarchy` 中存在
2. `sub_topic` 必须在对应 `parent_topic` 的 `sub_topics` 列表中

#### 3.3.4 `AsyncPublisherObjectAnalysisBatchNode`

| 属性 | 值 |
|:---|:---|
| **输出字段** | `publisher` (str) |
| **LLM 模型** | `call_glm_45_air`（纯文本） |
| **Temperature** | 0.3 |
| **Fallback** | `"个人用户"` |

**Prompt 策略**：
- 将候选发布者类型用顿号连接
- 额外传入发布者昵称/账号信息（`username` 或 `user_name`）辅助判断
- 要求直接输出候选列表中的一个条目

**验证逻辑**：输出必须在候选列表中，否则降级为 `"个人用户"`

#### 3.3.5 `AsyncBeliefSystemAnalysisBatchNode`

| 属性 | 值 |
|:---|:---|
| **输出字段** | `belief_signals` (List[Dict]) |
| **LLM 模型** | `call_glm_45_air`（纯文本） |
| **Temperature** | 0.2（更低，求稳定） |
| **Fallback** | `[]`（空列表） |

**特殊处理**：
- **文本清洗** `_clean()`：修正 UTF-8 内容被错误读取为 Latin-1 的常见乱码问题
- **多重 JSON 解析**：
  1. 检查 Markdown 代码块包裹 → 提取内部 JSON
  2. 查找 `[` 和 `]` 的位置 → 截取 JSON 数组
  3. 正则搜索 `[{...}]` 模式 → 二次解析尝试
  4. 以上均失败则返回空列表

**验证逻辑**：
- `category` 必须在信念体系定义中存在
- `subcategories` 中的每个子类必须在对应 `category` 的定义列表中

### 3.4 各节点 LLM 调用模型选择总结

| 节点 | 纯文本模型 | 视觉模型 | 条件 |
|:---|:---|:---|:---|
| SentimentPolarity | `call_glm_45_air` | `call_glm4v_plus` | 有 `image_urls` 时用视觉模型 |
| SentimentAttribute | `call_glm_45_air` | — | 仅文本 |
| TopicAnalysis | `call_glm_45_air` | `call_glm4v_plus` | 有 `image_urls` 时用视觉模型 |
| PublisherObject | `call_glm_45_air` | — | 仅文本 |
| BeliefSystem | `call_glm_45_air` | — | 仅文本 |

---

## 4. 数据加载与保存

### 4.1 `DataLoadNode`

| 属性 | 值 |
|:---|:---|
| **类型** | `Node` |
| **数据源** | 由 `config.data_source.type` 决定 |

#### 加载模式

| `data_source.type` | 行为 |
|:---|:---|
| `"original"` | 加载原始博文 + 5 个参考数据文件 |
| `"enhanced"` | 直接加载已增强的博文数据 |

#### Pipeline entry and resume boundary

`pipeline.start_stage` in `config.yaml` is the explicit pipeline entry and is not auto-advanced when `data.resume_if_exists` is true or when `data.output_path` already exists. Resume only applies after Stage1 is selected and `DataLoadNode` is running in `original` mode.

#### 断点续传逻辑（`original` 模式）

当 `data.resume_if_exists == True`（默认）且增强数据文件已存在时：

1. 加载已有的增强数据
2. 长度校验：`len(enhanced) == len(original)`
3. **抽样一致性校验**：取首、中、尾 3 条博文，比较 `content`、`publish_time`、`user_id`、`username` 4 个字段
4. 至少 2/3 匹配则认为数据集一致，使用增强数据（覆盖原始数据）
5. 不匹配则忽略已有增强数据，从头开始

#### `post` 写回 `shared`

- `shared["data"]["blog_data"]` ← 博文数据（原始或增强）
- `shared["data"]["topics_hierarchy"]` ← 主题层次结构
- `shared["data"]["sentiment_attributes"]` ← 情感属性列表
- `shared["data"]["publisher_objects"]` ← 发布者类型列表
- `shared["data"]["belief_system"]` ← 信念体系分类
- 初始化 `shared["stage1_results"]["statistics"]` 结构（详细的空值统计、参与度统计等）

### 4.2 `SaveEnhancedDataNode`

| 属性 | 值 |
|:---|:---|
| **类型** | `Node` |
| **输出路径** | `config.data_source.enhanced_data_path`（默认 `data/enhanced_blogs.json`） |

简单的保存节点：
1. **prep**：读取 `blog_data` 和输出路径
2. **exec**：调用 `save_enhanced_blog_data()` 工具函数
3. **post**：记录保存状态到 `shared["stage1_results"]["data_save"]`

---

## 5. 数据验证 `DataValidationAndOverviewNode`

### 5.1 概述

在增强处理完成后执行质量检查，生成详细的统计报告。

### 5.2 验证内容

| 统计类别 | 统计项 |
|:---|:---|
| **空值统计** | 5 个增强字段的空值计数（`sentiment_polarity_empty`、`sentiment_attribute_empty` 等） |
| **参与度统计** | 总转发/评论/点赞数、平均值 |
| **用户统计** | 独立用户数、活跃用户 Top10、发布者类型分布 |
| **内容统计** | 总图片数、含图博文数、平均内容长度、按小时的发布时间分布 |
| **地理分布** | IP 归属地分布（按 `ip_location` 字段） |

### 5.3 输出

- 将完整统计写入 `shared["stage1_results"]["statistics"]`
- 在控制台打印详细的验证报告（包含所有统计项的格式化输出）

---

## 6. 阶段完成 `Stage1CompletionNode`

| 行为 | 说明 |
|:---|:---|
| 将 `1` 追加到 `shared["pipeline_state"]["completed_stages"]` | 标记阶段 1 完成 |
| 更新 `shared["pipeline_state"]["current_stage"] = 1` | 记录当前阶段 |
| 返回 `"default"` | 在线性主链中顺序进入阶段 2 |
