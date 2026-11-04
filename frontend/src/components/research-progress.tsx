"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Job, AgentUpdate } from "@/lib/types";
import { artifactLabels } from "@/lib/i18n";
import { useI18n } from "./language-provider";
import { Card } from "./tremor/Card";
import { JobPanel } from "./job-panel";
import { StatusBadge, statusLabels } from "./ui";
import { UsageSummary } from "./usage-summary";
import { Bot, ShieldCheck, CircleCheck, CircleAlert, Clock3, LoaderCircle } from "lucide-react";

type TraceEvent = { id: number; timestamp: string; kind: string; stage?: string; role?: string; tool?: string; model?: string; message?: string; error_type?: string; traceback?: string; duration_seconds?: number; status?: string };
type AgentState = { status: string; stage?: string; action: string; updated_at?: string };
type Supervisor = { status: string; message: string; completed: number; total: number; next_stage?: string; elapsed_seconds: number; updated_at: string; agents: Record<string, AgentState> };
type Diagnosis = { summary: string; cause: string; evidence: string[]; suggestions: string[]; source: string; diagnostic_error?: string };
type Progress = { job: Job; stages: { task_id: string; role: string; operation: string; status: string }[]; events: TraceEvent[]; error?: TraceEvent; usage: Record<string, unknown>; supervisor?: Supervisor; diagnosis?: Diagnosis };
const agentNames: Record<string, string> = { SupervisorAgent: "流程监控", LeaderAgent: "研究规划", DataAgent: "数据分析", data: "数据审阅", search: "外部证据", visual: "可视化审阅", insight: "综合解读", methodology: "方法审查", ForumHost: "论坛主持", ContentAgent: "内容整理", SocialScienceAgent: "社科解读", ReportUIAgent: "报告编排", RecommendationAgent: "建议生成", DecisionModel: "决策标注", SamplingAgent: "热度抽样", SchemaAgent: "标签设计", LabelAgent: "数据标注", CollectorAgent: "数据采集" };
const eventNames: Record<string, string> = { started: "开始运行", stage_started: "阶段开始", stage_finished: "阶段完成", model_started: "模型调用", model_finished: "模型返回", tool_started: "工具调用", tool_finished: "工具返回", failed: "执行失败", model_failed: "执行失败", stage_error: "执行失败", waiting_for_auth: "等待授权", partial: "部分完成" };

export function ResearchProgress({ threadId, jobs, updates, onRefresh }: { threadId: string; jobs: Job[]; updates: AgentUpdate[]; onRefresh: () => void }) {
  const { t, locale } = useI18n();
  const [selected, setSelected] = useState("");
  const [value, setValue] = useState<Progress>();
  const [error, setError] = useState("");
  const [history, setHistory] = useState<AgentUpdate[]>([]);
  useEffect(() => {
    let live = true;
    api<AgentUpdate[]>(`/threads/${threadId}/activity`).then(data => { if (live) setHistory(data); }).catch(e => { if (live) setError(e.message); });
    return () => { live = false; };
  }, [threadId, updates]);
  const jobId = selected || jobs[0]?.job_id;
  useEffect(() => {
    let live = true; setValue(undefined); setError("");
    if (!jobId) return;
    const refresh = () => api<Progress>(`/threads/${threadId}/jobs/${jobId}/progress`).then(data => { if (live) { setValue(data); setError(""); } }).catch(e => { if (live) setError(e.message); });
    void refresh(); const timer = setInterval(refresh, 2000);
    return () => { live = false; clearInterval(timer); };
  }, [threadId, jobId]);
  const complete = value?.stages.filter(item => item.status === "completed").length ?? 0;
  const supervisor = value?.supervisor;
  const agents = Object.entries(supervisor?.agents ?? {}).filter(([role]) => role !== "SupervisorAgent");
  const live = ["queued", "running", "cancel_requested"].includes(value?.job.status ?? "");
  return <div className="progress-layout">
    {!!jobs.length && <label className="progress-run-picker">{t("选择研究任务")}<select value={jobId} onChange={e => setSelected(e.target.value)}>{jobs.map(job => <option key={job.job_id} value={job.job_id}>{job.run_id} · {t(statusLabels[job.status] ?? job.status)}</option>)}</select></label>}
    {error && <p role="alert" className="error">{error}</p>}
    {value && <>
      {supervisor && <Card className="surface supervisor-card"><div className="supervisor-heading"><div className="supervisor-icon"><ShieldCheck size={25} /></div><div><h2>{t("流程监控 Agent")}</h2><p role="status">{locale === "en-US" && supervisor.status === "running" ? `${t("当前阶段")} · ${t(artifactLabels[value.job.stage] ?? value.job.stage)}` : supervisor.message}</p></div><StatusBadge status={supervisor.status} /></div><div className="supervisor-meta"><span>{t("已完成 {done} / {total} 个阶段", {done: supervisor.completed, total: supervisor.total})}</span><span>{t("已运行")} {Math.floor(supervisor.elapsed_seconds / 60)}m {supervisor.elapsed_seconds % 60}s</span>{supervisor.next_stage && <span>{t("接下来")} · {t(artifactLabels[supervisor.next_stage] ?? supervisor.next_stage)}</span>}<span>{t("更新于")} {new Date(supervisor.updated_at).toLocaleTimeString(locale)}</span></div><progress max={supervisor.total || 1} value={supervisor.completed} aria-label={t("阶段进度")} /></Card>}
      {!!agents.length && <section><div className="section-heading"><h2>{t("智能体协作")}</h2><span className={`live-status ${live ? "online" : ""}`}><i />{t(live ? "实时同步" : "执行记录")}</span></div><div className="agent-grid">{agents.map(([role, agent]) => { const Icon = agent.status === "running" ? LoaderCircle : agent.status === "completed" ? CircleCheck : agent.status === "failed" ? CircleAlert : Clock3; return <Card className={`agent-card ${agent.status}`} key={role}><div className="agent-card-heading"><Bot size={19} /><strong>{t(agentNames[role] ?? artifactLabels[agent.stage ?? ""] ?? role)}</strong><Icon size={17} className={agent.status === "running" ? "agent-spinner" : ""} /></div><StatusBadge status={agent.status} /><p>{locale === "en-US" ? t(artifactLabels[agent.stage ?? ""] ?? agent.action) : agent.action}</p><small>{role}{agent.updated_at ? ` · ${new Date(agent.updated_at).toLocaleTimeString(locale)}` : ""}</small></Card>; })}</div></section>}
      {value.diagnosis && <Card className="surface diagnosis-card"><div className="section-heading"><h2>{t("监控 Agent 错误分析")}</h2><span>{t(value.diagnosis.source === "model" ? "模型诊断" : "本地诊断")}</span></div><h3>{value.diagnosis.summary}</h3><p>{value.diagnosis.cause}</p><strong>{t("错误依据")}</strong><ul>{value.diagnosis.evidence.map((item, i) => <li key={i}>{item}</li>)}</ul><strong>{t("处理建议")}</strong><ol>{value.diagnosis.suggestions.map((item, i) => <li key={i}>{item}</li>)}</ol>{value.diagnosis.diagnostic_error && <details><summary>{t("诊断服务信息")}</summary><p>{value.diagnosis.diagnostic_error}</p></details>}</Card>}
      <Card className="surface"><div className="section-heading"><h2>{t("阶段进度")}</h2><span>{t("已完成 {done} / {total} 个阶段", { done: complete, total: value.stages.length })}</span></div>
        <div className="stage-track">{value.stages.map(item => <div className={`stage-item ${item.status}`} key={item.task_id}><span className="stage-marker" /><div><strong>{t(artifactLabels[item.task_id] ?? item.task_id)}</strong><small>{item.role}</small></div><StatusBadge status={item.status} /></div>)}</div>
      </Card>
      {(value.error || value.job.status === "failed") && <Card className="surface failure-detail"><div className="section-heading"><h2>{t("失败详情")}</h2><StatusBadge status={value.job.status} /></div><p><strong>{t(artifactLabels[value.job.stage] ?? value.job.stage)} · {value.error?.error_type ?? value.job.error_type}</strong></p>
        <p className="error-message">{value.error?.message ?? t("该历史任务只保存了异常类型，未记录具体错误和调用栈。")}</p>
        {value.error?.traceback && <details><summary>{t("错误调用栈")}</summary><pre className="trace-output">{value.error.traceback}</pre></details>}
      </Card>}
      <UsageSummary value={value.usage} />
      <Card className="surface section-card"><details><summary>{t("运行日志")}</summary><div className="table-scroll"><table><thead><tr><th>{t("时间")}</th><th>{t("动作")}</th><th>{t("智能体 / 工具")}</th><th>{t("详情")}</th></tr></thead><tbody>{[...value.events].reverse().filter(item => !["supervisor_status", "supervisor_diagnosis"].includes(item.kind)).map(item => <tr key={item.id}><td>{new Date(item.timestamp).toLocaleTimeString(locale)}</td><td>{t(eventNames[item.kind] ?? item.kind)}</td><td>{item.role ?? item.tool ?? t(artifactLabels[item.stage ?? ""] ?? item.stage ?? "—")}</td><td className="trace-detail">{item.message ?? item.model ?? item.status ?? ""}{item.duration_seconds !== undefined ? ` · ${item.duration_seconds}s` : ""}{item.traceback && <details><summary>{t("错误调用栈")}</summary><pre className="trace-output">{item.traceback}</pre></details>}</td></tr>)}</tbody></table>{!value.events.length && <p className="compact-empty muted">{t("该任务尚无运行日志。阶段进度来自已保存的执行记录。")}</p>}</div></details></Card>
    </>}
    <details><summary>{t("任务记录与操作")}</summary><JobPanel threadId={threadId} jobs={jobs} active onRefresh={onRefresh} controlsOnly onInspect={setSelected} /></details>
    {!!history.length && <Card className="surface"><h2>Leader Agent</h2>{history.slice(-12).reverse().map((item, i) => <div className="leader-trace" key={i}><strong>{item.node ?? item.status ?? t("开始运行")}</strong><p>{item.reply ?? item.message ?? item.error_type ?? ""}</p>{item.traceback && <details><summary>{t("错误调用栈")}</summary><pre className="trace-output">{item.traceback}</pre></details>}</div>)}</Card>}
  </div>;
}
