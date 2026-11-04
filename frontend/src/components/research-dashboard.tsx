"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Database, Image, MessageSquare, TrendingUp } from "lucide-react";
import { api } from "@/lib/api";
import type { ArtifactRef, Thread } from "@/lib/types";
import { useI18n } from "./language-provider";
import { AnalysisChart, type ChartData } from "./analysis-chart";
import { ArtifactViewer } from "./artifact-viewer";
import { Card } from "./tremor/Card";
import { EmptyState } from "./ui";

type DatasetSummary = {
  dataset_id: string; metrics: Record<string, number>; missing: Record<string, number>;
  start: string | null; end: string | null; charts: Record<string, ChartData>;
  top_posts: { post_id: string; content: string; score: number; published_at: string | null }[];
};
type Dashboard = { thread_id: string | null; title?: string; dataset: DatasetSummary | null; charts: Record<string, ChartData>; report?: ArtifactRef; has_analysis?: boolean };

export function DatasetCharts({ value, compact = false, metricsOnly = false, chartsOnly = false }: { value: DatasetSummary; compact?: boolean; metricsOnly?: boolean; chartsOnly?: boolean }) {
  const { t, locale } = useI18n();
  return <>
    {!chartsOnly && <div className="metric-grid">
      {[
        ["帖子总量", "posts", Database], ["互动总量", "interactions", TrendingUp],
        ["含图帖子", "image_posts", Image], ["配图数量", "images", MessageSquare],
      ].map(([label, field, Icon]) => {
        const MetricIcon = Icon as typeof Database;
        return <Card className="surface metric-card" key={String(field)}><div className="metric-label">{t(String(label))}<MetricIcon size={18} /></div><div className="metric-value">{(value.metrics[String(field)] ?? 0).toLocaleString(locale)}</div></Card>;
      })}
    </div>}
    {!metricsOnly && <div className="dashboard-chart-grid">
      {Object.entries(value.charts).filter(([key]) => !compact || !["missing", "regions"].includes(key)).map(([name, chart]) => <Card className="surface" key={name}><AnalysisChart name={name} value={{ ...chart, title: t(chart.title ?? name) }} /></Card>)}
    </div>}
    {!compact && <Card className="surface section-card"><div className="section-heading"><h2>{t("高互动帖子")}</h2><span className="muted">{t("热度 = 点赞 + 评论 + 转发")}</span></div>
      <div className="table-scroll"><table><thead><tr><th>{t("帖子内容")}</th><th>{t("发布时间")}</th><th>{t("互动热度")}</th></tr></thead><tbody>{value.top_posts.map((row, i) => <tr key={row.post_id ?? i}><td className="post-excerpt">{row.content}</td><td>{row.published_at ? new Date(row.published_at).toLocaleDateString(locale) : "—"}</td><td>{row.score.toLocaleString(locale)}</td></tr>)}</tbody></table></div>
    </Card>}
  </>;
}

export function DatasetOverview({ threadId, datasetId }: { threadId: string; datasetId: string }) {
  const { t } = useI18n();
  const [value, setValue] = useState<DatasetSummary>();
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true; setValue(undefined); setError("");
    if (datasetId) api<DatasetSummary>(`/threads/${threadId}/datasets/${datasetId}/overview`).then(data => { if (live) setValue(data); }).catch(e => { if (live) setError(e.message); });
    return () => { live = false; };
  }, [threadId, datasetId]);
  if (error) return <p role="alert" className="error">{error}</p>;
  if (!value) return <p className="muted">{t(datasetId ? "正在读取数据统计…" : "选择数据版本以查看统计图表。")}</p>;
  return <DatasetCharts value={value} />;
}

export function ResearchDashboard({ threads, refreshKey }: { threads: Thread[]; refreshKey: number }) {
  const { t } = useI18n();
  const [selected, setSelected] = useState("");
  const [value, setValue] = useState<Dashboard>();
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    const refresh = () => api<Dashboard>(`/overview${selected ? `?thread_id=${selected}` : ""}`).then(data => { if (live) { setValue(data); setError(""); } }).catch(e => { if (live) setError(e.message); });
    setValue(undefined); void refresh(); const timer = setInterval(refresh, 15000);
    return () => { live = false; clearInterval(timer); };
  }, [selected, refreshKey]);
  return <div className="dashboard-layout">
    <div className="dashboard-toolbar"><h1>{t("研究概览")}</h1><div className="actions">
      <select aria-label={t("选择看板事件")} value={selected} onChange={e => setSelected(e.target.value)}><option value="">{t("最近分析 / Demo")}</option>{threads.map(item => <option value={item.thread_id} key={item.thread_id}>{item.title}</option>)}</select>
      {value?.thread_id && <Link className="text-link" href={`/workspace/chats/${value.thread_id}`}>{t("进入研究")}<ArrowUpRight size={16} /></Link>}
    </div></div>
    {error && <p role="alert" className="error">{error}</p>}
    {!value && !error && <p className="loading-text">{t("正在读取数据统计…")}</p>}
    {value?.dataset && <DatasetCharts value={value.dataset} compact metricsOnly />}
    {!!Object.keys(value?.charts ?? {}).length && <section><h2 className="dashboard-section-title">{t("分析结果")}</h2><div className="dashboard-chart-grid">{Object.entries(value!.charts).map(([name, chart]) => <Card className="surface" key={name}><AnalysisChart name={name} value={chart} /></Card>)}</div></section>}
    {value?.dataset && <DatasetCharts value={value.dataset} compact chartsOnly />}
    {value?.report && value.thread_id && <Card className="surface"><ArtifactViewer threadId={value.thread_id} reference={value.report} /></Card>}
    {value && !value.dataset && !value.thread_id && <Card className="surface"><EmptyState title={t("开始你的第一项事件研究")} description={t("导入数据后，统计图表会显示在这里。")} /></Card>}
  </div>;
}
