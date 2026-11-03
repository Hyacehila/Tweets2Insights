# MCP Tool Audit

- Last Updated: 2026-11-03

- Total tool_registry entries: 42
- MCP exposed tools (unique): 76
- Missing registry tools: 0

## Missing Tools

- None

## Mapping (tool_registry → MCP public name)

| tool_registry | mcp_tool | generates_chart | category |
|---|---|---|---|
| belief_network_chart | belief_network_chart | True | 信念系统分析 |
| correlation_analysis | correlation_analysis | False | 多维交互分析 |
| cross_dimension_matrix | cross_dimension_matrix | True | 多维交互分析 |
| entity_cooccurrence_network | entity_cooccurrence_network | True | NLP增强分析 |
| geographic_bar_chart | geographic_bar_chart | True | 地理分布分析 |
| geographic_distribution_stats | geographic_distribution_stats | True | 地理分布分析 |
| geographic_heatmap | geographic_heatmap | True | 地理分布分析 |
| geographic_hotspot_detection | geographic_hotspot_detection | True | 地理分布分析 |
| geographic_sentiment_analysis | geographic_sentiment_analysis | True | 地理分布分析 |
| geographic_sentiment_bar_chart | geographic_sentiment_bar_chart | True | 地理分布分析 |
| geographic_temporal_heatmap | geographic_temporal_heatmap | True | 地理分布分析 |
| geographic_topic_heatmap | geographic_topic_heatmap | True | 地理分布分析 |
| influence_analysis | influence_analysis | False | 多维交互分析 |
| interaction_heatmap | interaction_heatmap | True | 多维交互分析 |
| keyword_wordcloud | keyword_wordcloud | True | NLP增强分析 |
| participant_trend_chart | participant_trend_chart | True | 多维交互分析 |
| publisher_bar_chart | publisher_bar_chart | True | 多维交互分析 |
| publisher_distribution_stats | publisher_distribution_stats | True | 多维交互分析 |
| publisher_focus_distribution_chart | publisher_focus_distribution_chart | True | 焦点窗口分析 |
| publisher_sentiment_bucket_chart | publisher_sentiment_bucket_chart | True | 多维交互分析 |
| publisher_topic_distribution_chart | publisher_topic_distribution_chart | True | 多维交互分析 |
| sentiment_anomaly_detection | sentiment_anomaly_detection | False | 情感趋势分析 |
| sentiment_attribute_trend_chart | sentiment_attribute_trend_chart | True | 情感趋势分析 |
| sentiment_bucket_trend_chart | sentiment_bucket_trend_chart | True | 情感趋势分析 |
| sentiment_distribution_stats | sentiment_distribution_stats | True | 情感趋势分析 |
| sentiment_focus_publisher_chart | sentiment_focus_publisher_chart | True | 焦点窗口分析 |
| sentiment_focus_window_chart | sentiment_focus_window_chart | True | 焦点窗口分析 |
| sentiment_lexicon_comparison | sentiment_lexicon_comparison | True | NLP增强分析 |
| sentiment_pie_chart | sentiment_pie_chart | True | 情感趋势分析 |
| sentiment_time_series | sentiment_time_series | True | 情感趋势分析 |
| sentiment_trend_chart | sentiment_trend_chart | True | 情感趋势分析 |
| temporal_keyword_heatmap | temporal_keyword_heatmap | True | NLP增强分析 |
| text_cluster_analysis | text_cluster_analysis | True | NLP增强分析 |
| topic_cooccurrence_analysis | topic_cooccurrence_analysis | True | 主题演化分析 |
| topic_evolution_chart | topic_evolution_chart | True | 主题演化分析 |
| topic_focus_distribution_chart | topic_focus_distribution_chart | True | 焦点窗口分析 |
| topic_focus_evolution_chart | topic_focus_evolution_chart | True | 主题演化分析 |
| topic_frequency_stats | topic_frequency_stats | True | 主题演化分析 |
| topic_keyword_trend_chart | topic_keyword_trend_chart | True | 主题演化分析 |
| topic_network_chart | topic_network_chart | True | 主题演化分析 |
| topic_ranking_chart | topic_ranking_chart | True | 主题演化分析 |
| topic_time_evolution | topic_time_evolution | True | 主题演化分析 |

PR-02：保持工具名不变，移除全局 blog_data 缓存；所有显式图表目录改用运行上下文。

独立领域服务新增 7 个工具：register_dataset、describe_dataset、read_evidence、render_report、read_artifact、job_status、cancel_job。与旧 76 个工具分别发现，不合并统计。

第二轮领域服务新增 submit_inventory_job/list_jobs/retry_job/read_job_artifact，共 11 项。旧同步接口保持兼容。

全项目架构重写新增 preview_plan、submit_run、list_datasets、list_artifacts、read_domain_artifact、resume_job，
领域 MCP 共 17 项。新领域运行不加载原 76 项旧标签工具；数值与长任务通过持久计划执行。
完整工作流新增 analysis_tool_catalog 与 submit_analysis_tool，领域 MCP 合计 19 项；分别用于查询 41 个分析入口和提交独立补充分析。
