# 领域契约与历史迁移

更新：2026-11-03。契约源码位于 backend/src/domain/opinion_core/schemas；默认主链为新工作台与领域 Worker，PocketFlow 仅保留兼容。

`opinion_core/schemas/` 使用 Pydantic 严格拒绝未知字段，`contract_version=1`。
EventSpec 固定输入模式和搜索供应商；上传/已有数据必须有 dataset_ref，关键词采集需要 keywords。
时间必须带时区并归一化 UTC，窗口为 `[start,end)` 且 end 不超过 as_of。
EventSchema 的类别只有 ID 与定义，无层级；证据引用不能为空。准备服务已实现搜索前置、采样上下文和冻结缓存。

PostRecord 保留原始 ID、时间、来源和媒体引用。缺失或无法解释的发布时间为 null；采集时间不能替代发布时间。
可选 region、read_count、like_count、comment_count、repost_count 保留地区和互动事实；缺失为 null，不能自动填零。
parent_ref 是同平台父帖的原始 ID；thread_ref 可保存平台原生讨论线程 ID。话题共现优先按 thread_ref 分组，
否则沿已知父引用查找线程根；不能把单标签帖子解释为多话题共现。
AnnotationRecord 每字段分别存 accepted/abstained/failed/missing；只有 accepted 带值。
provider_confidence 单列模型自报置信度，不能自动当作 probability；自动标注入口不声称已完成置信度校准。
原生 System One 可保存 probabilities、被选类别 probability 和 probability_margin；这些均是供应商输出/派生量，独立 Demo 才能评估校准质量。
立场只接受 support/oppose/neutral 且必须绑定 target_id；情感为 [-1,1] 显示编码。
RunManifest 保存数据、代码、schema、模型、提示词版本、seed、预算与配置，拒绝含凭据名称的配置字段。

```python
from opinion_core.ingestion.legacy_adapter import migrate_file
migrate_file('data/old.json', 'data/migrated-v1.json', schema_version='event-v1',
             mapping_version='map-v1', topic_map={('社会民生', '居民生活'): 'life'},
             source_timezone='Asia/Shanghai')
```

迁移支持旧 `topics` 列表与 `topic` 单值，只在所有旧主题显式映射到同一个主主题时接收。
多义/未映射主题拒判。情感 1–5 以 `(score-3)/2` 编码；不推导立场。
旧发布者、情绪词未经新事件词库映射仍标缺失，待重标注。原字段完整归档，迁移清单记录
源 SHA256、映射版本、时区、数量、归档字段、丢失字段和重标注数量。输出必须为新文件。
`legacy-unverified` 表示旧标签质量未验证；不能当作通过新标注质量门槛的数据。

验证：契约/迁移、现有数据格式和 Stage1 节点测试。新增实际 Stage1 fixture 的 topics 列表回归。
M0 质量/覆盖率/金标准规模已登记于[弱标注 Demo 协议](../testing/weak-label-demo-protocol.md)，人工验证仅用于 Demo。
正式运行以自动校验后的模型弱标注进入分析，不要求逐批人工复核；当前仍无真实标注成本或质量结论。
后续阶段见[升级记录](../upgrade-status.md)。
