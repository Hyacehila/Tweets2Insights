"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
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
  const ids = jobs.filter(job => ["completed", "partial"].includes(job.status)).map(job => job.job_id).join(",");
  useEffect(() => {
    let live = true; setLoading(true);
    Promise.all(ids.split(",").filter(Boolean).map(async id => ({ run: id, result: await api<DomainResult>(`/threads/${threadId}/jobs/${id}/result`) }))).then(values => { if (live) { setReports(values.filter(item => item.result.artifacts?.report)); setError(""); } }).catch(e => { if (live) setError(e.message); }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [threadId, ids]);
  const report = reports.find(item => item.run === selected) ?? reports[0];
  return <Card className="surface">
    <div className="section-heading"><h2>{t("分析与报告")}</h2>{reports.length > 1 && <select aria-label={t("报告版本")} value={report?.run} onChange={e => setSelected(e.target.value)}>{reports.map(item => <option key={item.run} value={item.run}>{item.result.artifacts!.report.run_id}</option>)}</select>}</div>
    {error && <p role="alert" className="error">{error}</p>}
    {loading ? <p className="loading-text">{t("正在读取研究产物…")}</p> : report ? <ArtifactViewer threadId={threadId} reference={report.result.artifacts!.report} /> : <EmptyState title={t("尚无分析报告")} description={t("报告生成后将在这里展示完整的分析、图表与结论。")} />}
  </Card>;
}
