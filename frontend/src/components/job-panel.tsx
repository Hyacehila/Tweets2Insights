"use client";
import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import type { Job, DomainResult, ArtifactRef } from "@/lib/types";
import { ArtifactViewer } from "./artifact-viewer";

const labels: Record<string, string> = { queued: "排队中", running: "执行中", waiting_for_auth: "等待登录", cancelled: "已取消", cancel_requested: "正在取消", partial: "部分完成", completed: "已完成", failed: "失败" };
export function JobPanel({ threadId }: { threadId: string }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [result, setResult] = useState<DomainResult>({});
  const [artifact, setArtifact] = useState<ArtifactRef>();
  const [error, setError] = useState("");
  const [tools,setTools]=useState<{name:string;description:string}[]>([]);
  const [tool,setTool]=useState("sentiment_time_series"),[parameters,setParameters]=useState("{}");
  useEffect(()=>{api<{name:string;description:string}[]>("/analysis-tools").then(setTools).catch(()=>{});},[]);
  useEffect(() => {
    setJobs([]); setSelected(""); setResult({}); setArtifact(undefined); setError("");
    let live = true;
    const refresh = () => api<Job[]>(`/threads/${threadId}/jobs`).then((items) => { if (live) { setJobs(items); setError(""); } }).catch((e: Error) => { if (live) setError(e.message); });
    void refresh(); const timer = setInterval(refresh, 5000);
    return () => { live = false; clearInterval(timer); };
  }, [threadId]);
  useEffect(() => {
    setResult({}); setArtifact(undefined);
    if (!selected) return;
    let live = true;
    api<DomainResult>(`/threads/${threadId}/jobs/${selected}/result`).then((data) => { if (live) setResult(data); }).catch((e: Error) => { if (live) setError(e.message); });
    return () => { live = false; };
  }, [selected, threadId]);
  async function action(job: Job, name: string) {
    try { await post(`/threads/${threadId}/jobs/${job.job_id}/${name}`, {}); setJobs(await api(`/threads/${threadId}/jobs`)); }
    catch (e) { setError((e as Error).message); }
  }
  async function supplement(){
    try{await post(`/threads/${threadId}/jobs/${selected}/analysis-tools/${tool}`,JSON.parse(parameters));setJobs(await api(`/threads/${threadId}/jobs`));setError("");}
    catch(e){setError((e as Error).message);}
  }
  return <section className="job-panel">
    <div className="section-heading"><h2>运行与产物</h2><span>{jobs.length} 个任务</span></div>
    {error && <p className="error">{error}</p>}
    {!jobs.length && <p className="empty">提交计划后，各阶段的进度和产物会出现在这里。</p>}
    {jobs.map((job) => <article className="job-card" key={job.job_id}>
      <div><strong>{job.run_id}</strong><span className={`badge ${job.status}`}>{labels[job.status] ?? job.status}</span></div>
      <p>{job.stage || "等待 Worker"}{job.error_type && ` · ${job.error_type}`}</p>
      <div className="actions">
        {["queued", "running", "waiting_for_auth"].includes(job.status) && <button onClick={() => action(job, "cancel")}>取消</button>}
        {["partial", "failed", "cancelled"].includes(job.status) && <button onClick={() => action(job, "retry")}>重试</button>}
        {job.status === "waiting_for_auth" && <button onClick={() => action(job, "resume")}>登录就绪后恢复</button>}
        {["completed", "partial"].includes(job.status) && <button onClick={() => setSelected(job.job_id)}>查看产物</button>}
      </div>
    </article>)}
    {result.artifacts && <>{result.artifacts.labels&&<details><summary>基于本次冻结标签补充分析</summary><label>工具<select value={tool} onChange={e=>setTool(e.target.value)}>{tools.map(t=><option key={t.name} value={t.name}>{t.description}</option>)}</select></label><label>参数 JSON<textarea value={parameters} onChange={e=>setParameters(e.target.value)}/></label><button onClick={supplement}>提交补充分析</button></details>}<div className="artifact-tabs">{Object.entries(result.artifacts).map(([key, ref]) => <button key={key} onClick={() => setArtifact(ref)}>{key}</button>)}</div>
      {artifact && <ArtifactViewer threadId={threadId} reference={artifact} />}</>}
  </section>;
}
