# 工具函数文档

> **文档状态**: 2026-11-04 更新
> **关联源码**: `utils/call_llm.py`, `utils/llm_retry.py`, `utils/data_loader.py`, `utils/console_safe.py`, `utils/path_manager.py`, `utils/status_events.py`, `utils/status_store.py`, `utils/trace_manager.py`, `utils/web_search.py`, `utils/data_sources/*`, `utils/nlp/*`  
> **上级文档**: [系统设计总览](../architecture.md)

---

## 1. LLM 调用层 `call_llm.py`

### 1.1 模型概览

系统使用智谱 AI（Zhipu AI）的 GLM 系列模型，通过 `zai-sdk` 进行调用。

| 调用函数 | 底层模型 | 类型 | 主要用途 | 默认温度 |
|:---|:---|:---|:---|:---|
| `call_glm_45_air` | `glm-4.5-air` | 纯文本 | 阶段 1 数据增强 | 0.7 |
| `call_glm4v_plus` | `glm-4v-plus` | 多模态（文本+图像） | 图像理解与视觉分析 | 0.7 |
| `call_glm45v_thinking` | `glm-4.5v` | 多模态（文本+图像） | 图表视觉分析 | 0.7 |
| `call_glm46` | `glm-4.6` | 纯文本+推理 | Agent 决策、洞察生成、报告撰写 | 0.8 |

> `call_glm4v_plus` 使用 `glm-4v-plus` 视觉模型，支持 `image_paths` / `image_data` 输入并进行 base64 编码。

### 1.2 客户端管理

**ThreadLocal 模式**：

```python
_thread_local = threading.local()

def get_client():
    api_key = os.getenv("GLM_API_KEY")
    if not api_key:
        raise RuntimeError("GLM_API_KEY environment variable is not set.")
    if not hasattr(_thread_local, "client") or getattr(_thread_local, "api_key", None) != api_key:
        _thread_local.client = ZaiClient(api_key=api_key)
        _thread_local.api_key = api_key
    return _thread_local.client
```

- 每个线程独立持有一个 `ZaiClient` 实例
- 避免锁竞争，同时实现连接复用
- 适配阶段 1 的高并发异步批处理场景（60+ 并发信号量）
- API Key 来源：`config.yaml` 的 `llm.glm_api_key` 优先（运行时会写入 `GLM_API_KEY`），否则读取环境变量 `GLM_API_KEY`

### 1.3 `call_glm_45_air` 详细说明

| 参数 | 类型 | 默认值 | 说明 |
|:---|:---|:---|:---|
| `prompt` | `str` | — | 输入提示词 |
| `temperature` | `float` | 0.7 | 控制随机性 |
| `max_tokens` | `int?` | `None` | 最大生成 token 数 |
| `enable_thinking` | `bool` | `False` | 思考模式（此模型不支持，参数保留） |
| `timeout` | `int` | 30 | 请求超时秒数 |

**错误分类处理**：
- 429 / rate limit → 抛出 "API速率限制" 异常
- timeout → 抛出 "请求超时" 异常
- 其他 → 抛出通用异常

### 1.4 `call_glm45v_thinking` 详细说明

| 参数 | 类型 | 默认值 | 说明 |
|:---|:---|:---|:---|
| `prompt` | `str` | — | 输入提示词 |
| `image_paths` | `List[str]?` | `None` | 图片文件路径列表 |
| `image_data` | `List[bytes]?` | `None` | 图片二进制数据（与 `image_paths` 二选一） |
| `temperature` | `float` | 0.7 | 控制随机性 |
| `max_tokens` | `int?` | `None` | 最大生成 token 数 |
| `enable_thinking` | `bool` | `True` | 开启思考模式 |

**图像编码流程**：
1. 读取图片文件 → `base64.b64encode`
2. 判断 MIME 类型：`.png` → `image/png`，其他 → `image/jpeg`
3. 构建 `data:URI` 格式：`data:{mime};base64,{data}`
4. 组装为 `{"type": "image_url", "image_url": {"url": "..."}}`

**思考模式参数**：
```python
if enable_thinking:
    params["thinking"] = {"enabled": True}
```

### 1.5 `call_glm46` 详细说明

| 参数 | 类型 | 默认值 | 说明 |
|:---|:---|:---|:---|
| `prompt` | `str` | — | 输入提示词 |
| `temperature` | `float` | 0.8 | 控制随机性 |
| `max_tokens` | `int?` | `None` | 最大生成 token 数 |
| `enable_reasoning` | `bool` | `True` | 开启推理模式 |
| `max_retries` | `int` | 3 | 保留参数（由统一重试装饰器处理） |
| `retry_delay` | `int` | 5 | 保留参数（由统一重试装饰器处理） |

**推理模式参数**：
```python
if enable_reasoning:
    params["thinking"] = {"enabled": True}
```

### 1.6 统一重试装饰器 `llm_retry`

`utils/llm_retry.py` 提供统一的 LLM 重试策略（默认线性退避），并已应用到：
- `call_glm_45_air`
- `call_glm4v_plus`
- `call_glm45v_thinking`
- `call_glm46`

---

## 2. 数据加载层 `data_loader.py`

### 2.1 函数概览

| 函数 | 功能 | 输入 | 输出 |
|:---|:---|:---|:---|
| `load_blog_data` | 加载原始博文数据 | `data/posts.json` | `List[Dict]` |
| `load_topics` | 加载主题分类 | `data/topics.json` | `List[Dict]`（含 `parent_topic` + `sub_topics`） |
| `load_sentiment_attributes` | 加载情感属性列表 | `data/sentiment_attributes.json` | `List[str]` |
| `load_publisher_objects` | 加载发布者类型列表 | `data/publisher_objects.json` | `List[str]` |
| `load_belief_system` | 加载信念体系分类 | `data/believe_system_common.json` | `List[Dict]`（含 `category` + `subcategories`） |
| `save_enhanced_blog_data` | 保存增强后数据 | 数据 + 路径 | `bool` |
| `load_enhanced_blog_data` | 加载增强后数据 | 路径 | `List[Dict]` |
| `save_analysis_results` | 保存分析结果 | 结果字典 + 路径 | `bool` |
| `load_analysis_results` | 加载分析结果 | 路径 | `Dict` |
| `check_stage_output_exists` | 检查阶段输出文件 | 阶段编号 | `Dict[str, bool]` |
| `get_sample_posts` | 博文抽样 | 数据 + 数量 + 策略 | `List[Dict]` |

### 2.2 `save_enhanced_blog_data` 原子写入

```python
# 先写入临时文件，再原子替换
temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
json.dump(data, temp_file, ensure_ascii=False, indent=2)
os.replace(temp_file.name, output_path)  # 原子替换
```

### 2.3 `check_stage_output_exists` 检查项

| 阶段 | 检查文件 |
|:---|:---|
| 1 | `data/enhanced_blogs.json` |
| 2 | `report/analysis_data.json`, `report/chart_analyses.json`, `report/insights.json`, `report/images/` |
| 3 | `report/report.md` |

### 2.4 `get_sample_posts` 三种抽样策略

| 策略 | 算法 | 适用场景 |
|:---|:---|:---|
| `random` | `random.sample()` | 通用抽样 |
| `influential` | 按 `repost_count + comment_count + like_count` 降序排列取 Top N | 高影响力案例 |
| `diverse` | 按情感极性分组 → 每组等比例抽取 → 随机填充不足部分 | 确保多样性覆盖 |

---

## 3. 辅助工具

### 3.1 `console_safe.py`

解决 Windows 控制台 Unicode 编码问题：

| 函数 | 说明 |
|:---|:---|
| `safe_print(text)` | 捕获 `UnicodeEncodeError`，用 ASCII 替换无法显示的字符 |
| `format_status_indicator(status)` | 返回 `[OK]` / `[X]`，避免 Emoji/特殊字符 |

### 3.2 `extract_test_posts.py`

从 `data/posts.json` 提取前 N 条数据，保存为 `data/test_posts.json`。

- 默认提取 100 条
- 打印统计信息：总条目数、有图片条目数、总图片数
- 显示前 3 条预览

### 3.3 `fix_posts_images.py`

修复博文数据中的图片数量（限制最多 3 张）：

- 遍历所有博文，截断 `image_urls` 至 ≤ 3 条
- 自动创建 `_backup.json` 备份文件
- 打印修复统计信息

---

## 4. 路径管理 `path_manager.py`

统一管理报告与图表输出目录：

- `get_report_dir()` → `report/`
- `get_images_dir()` → `report/images/`

所有图表工具通过 PathManager 确保输出目录存在。

---

## 5. 状态事件追踪 `status_events.py`

节点运行状态统一写入 `report/status.json`，仅记录**节点进入/退出事件**（enter/exit）：

```json
{
  "version": 2,
  "run_id": "uuid",
  "events": [
    {
      "seq": 1,
      "ts": "2026-02-20T00:00:00Z",
      "event": "enter",
      "stage": "stage2",
      "node": "SearchSummaryNode",
      "branch_id": "main",
      "status": "",
      "error": ""
    }
  ]
}
```

说明：

- `nodes.base.MonitoredNode / MonitoredAsyncNode` 在节点开始时写 `enter`，结束时写 `exit`（`completed/failed`）。
- 并行节点通过 `branch_id` 区分分支（例如 `data_agent` / `search_agent`），仍写入同一个 `status.json` 事件流。
- 事件写入使用 `status_store.atomic_write_json`，保证落盘原子替换。

### 5.1 相关回归测试

- `tests/unit/core/test_status_events.py`
- `tests/unit/core/test_node_status_events.py`
- `tests/unit/stage2/test_stage2_parallel_flow.py`（并行分支 `branch_id` 事件）

---

## 6. 数据源适配 `data_sources/`

当前仅实现 JSON 数据源：

- `JsonDataSource`：封装 `data_loader` 的加载逻辑，供 Stage1 `DataLoadNode` 使用。

---

## 7. 本地 NLP 工具 `utils/nlp/`

提供轻量文本处理能力（不依赖外部模型）：

- `text_cleaner`：清洗 URL/HTML/Emoji
- `tokenizer`：分词（优先 `jieba`，模块加载时显式 `jieba.initialize()`；失败时自动降级到正则 fallback，且中文连续词按 `[\u4e00-\u9fff]+` 提取）
- `keyword_extractor`：关键词抽取
- `ner`：规则实体抽取（#话题#, @用户）
- `sentiment_lexicon`：词典情感
- `similarity`：文本相似度聚类（sklearn + fallback）

---

## 8. 追溯管理 `trace_manager.py`

用于 Stage2 追溯数据统一写入与落盘，避免节点内重复拼装 trace 结构。

| 函数 | 输入 | 输出 |
|:---|:---|:---|
| `init_trace` | `shared` | 初始化并返回 `shared["trace"]` |
| `append_decision` | action/tool/reason/iteration | 追加 `decisions[]` 并返回 `decision_id` |
| `append_execution` | status/summary/decision_ref 等 | 追加 `executions[]` 并返回 `execution_id` |
| `append_reflection` | iteration + result | 追加 `reflections[]` 并返回 `reflection_id` |
| `set_insight_provenance` | provenance 字典 | 覆盖 `insight_provenance` |
| `build_lite_confidence` | evidence 列表 | `(high/medium/low, reason)` |
| `dump_trace_json` | trace + output_path | 写入 `report/trace.json` |

---

## 9. 搜索封装 `web_search.py`

用于 Stage2 QuerySearchFlow 的网络搜索能力，支持用户单选 `tavily` 或 `deepseek`；完整说明见 [搜索供应商](search-providers.md)。

### 9.1 函数概览

| 函数 | 输入 | 输出 |
|:---|:---|:---|
| `search_web` | `query` + provider/key/limit/timeout | `{query, provider, results[], error}` |
| `batch_search` | `queries[]` + provider/key/limit/timeout | `{queries, provider, results_by_query[], total_results}` |

### 9.2 API Key 解析顺序

1. 显式参数 `api_key`  
2. `config.yaml.stage2.search_api_key`（调用方传入）  
3. 所选供应商环境变量 `TAVILY_API_KEY` 或 `DEEPSEEK_API_KEY`  

若以上均为空，抛出 `EnvironmentError`。

### 9.3 标准化结果结构

每条结果统一输出：

```json
{
  "title": "...",
  "url": "...",
  "snippet": "...",
  "date": "...",
  "source": "..."
}
```

调用失败时不抛异常到上层，返回 `error` 字段并给出空 `results`，便于在流程中统一处理失败分支。

## 运行上下文与持久作业（2026-11-03）

run_context 将 report/images 和旧锁文件定位到 event/dataset/run 目录；默认入口不绑定上下文时保留兼容行为。新作业的状态事实源为 opinion_gateway.jobs.JobStore 的 SQLite 表，旧锁只服务旧流程。详见 [升级记录](../upgrade-status.md)。
