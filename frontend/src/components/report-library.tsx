"use client";
import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import type { DomainResult, Job } from "@/lib/types";
import { useI18n } from "./language-provider";
import { ArtifactViewer } from "./artifact-viewer";
import { Card } from "./tremor/Card";
import { EmptyState } from "./ui";

export function ReportLibrary({ threadId, jobs }: { threadId: string; jobs: Job[] }) {
  const { t } = useI18n();
  const [reports, setReports] = useState<{ run: string; result: DomainResult }[]>([]);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitted, setSubmitted] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const running = jobs.some(job => job.kind === "report_run" && ["queued", "running", "cancel_requested"].includes(job.status));
  const ids = jobs.filter(job => ["completed", "partial"].includes(job.status)).map(job => job.job_id).join(",");
  useEffect(() => {
    let live = true; setLoading(true);
    Promise.all(ids.split(",").filter(Boolean).map(async id => ({ run: id, result: await api<DomainResult>(`/threads/${threadId}/jobs/${id}/result`) }))).then(values => { if (live) { setReports(values.filter(item => item.result.artifacts?.report)); setError(""); } }).catch(e => { if (live) setError(e.message); }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [threadId, ids]);
  const report = reports.find(item => item.run === selected) ?? reports[0];
  async function regenerate() {
    const source = report?.run ?? jobs.find(job => ["completed", "partial"].includes(job.status) && job.kind === "analysis_run")?.job_id;
    if (!source) return;
    setSubmitting(true); setError("");
    try { const job = await post<Job>(`/threads/${threadId}/jobs/${source}/report`, {}); setSubmitted(job.job_id); }
    catch (e) { setError((e as Error).message); } finally { setSubmitting(false); }
  }
  return <Card className="surface">
    <div className="section-heading"><h2>{t("分析与报告")}</h2><div className="actions">{reports.length > 1 && <select aria-label={t("报告版本")} value={report?.run} onChange={e => setSelected(e.target.value)}>{reports.map(item => <option key={item.run} value={item.run}>{item.result.artifacts!.report.run_id}</option>)}</select>}<button onClick={regenerate} disabled={submitting || running || !!submitted && !jobs.some(j => j.job_id === submitted) || !report && !jobs.some(j => j.kind === "analysis_run" && ["completed", "partial"].includes(j.status))}>{t(running || submitting ? "正在生成报告…" : "重新生成报告")}</button></div></div>
    {(running || submitted) && <p className="muted">{t("报告任务已提交，可在研究进程追踪查看逐章进度。")}</p>}
    {error && <p role="alert" className="error">{error}</p>}
    {loading ? <p className="loading-text">{t("正在读取研究产物…")}</p> : report ? <ArtifactViewer threadId={threadId} reference={report.result.artifacts!.report} /> : <EmptyState title={t("尚无分析报告")} description={t("报告生成后将在这里展示完整的分析、图表与结论。")} />}
  </Card>;
}
