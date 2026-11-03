"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, post } from "@/lib/api";
import type { Thread, Dataset } from "@/lib/types";
import { useThreadStream } from "@/hooks/use-thread-stream";
import { JobPanel } from "./job-panel";
import { WorkflowBuilder, ProviderSettings } from "./workflow-builder";

export function Workspace({ threadId }: { threadId?: string }) {
  const router = useRouter();
  const [threads, setThreads] = useState<Thread[]>([]);
  const [thread, setThread] = useState<Thread>();
  const [event, setEvent] = useState("rain");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [dataset, setDataset] = useState("");
  const [provider, setProvider] = useState("tavily");
  const [keywords, setKeywords] = useState("");
  const [requestText, setRequestText] = useState("");
  const [requestDirty,setRequestDirty]=useState(false);
  const [execution, setExecution] = useState("");
  const { updates, connected } = useThreadStream(threadId);
  const latest = updates.at(-1);
  useEffect(() => { api<Thread[]>("/threads").then(setThreads).catch((e: Error) => setError(e.message)); }, [threadId]);
  useEffect(() => {
    setThread(undefined); setDatasets([]); setDataset(""); setMessage(""); setBusy(false);
    setRequestText(""); setError(""); setExecution("");
    setRequestDirty(false);
    if (!threadId) return;
    let live = true;
    api<Thread>(`/threads/${threadId}`).then((value) => {
      if (!live) return;
      setThread(value);
      const run = value.latest_execution;
      if (run?.status === "running") { setBusy(true); setExecution(run.execution_id); }
      if (run?.status === "interrupted") setError("上次 Agent 运行因服务重启中断，请检查已有任务后重新规划。");
    }).catch((e: Error) => { if (live) setError(e.message); });
    api<Dataset[]>(`/threads/${threadId}/datasets`).then((value) => { if (live) setDatasets(value); }).catch((e: Error) => { if (live) setError(e.message); });
    api<{ run_request?: unknown }>(`/threads/${threadId}/state`).then((s) => { if (live && s.run_request) setRequestText(JSON.stringify(s.run_request, null, 2)); }).catch(() => {});
    return () => { live = false; };
  }, [threadId]);
  useEffect(() => {
    if (!latest) return;
    if (latest.run_request) setRequestText(JSON.stringify(latest.run_request, null, 2));
    if (["completed", "failed", "cancelled"].includes(latest.status ?? "")) {
      setBusy(false);
      if (latest.error_type) setError(`运行失败：${latest.error_type}`);
      if (threadId) api<Thread>(`/threads/${threadId}`).then(setThread).catch(() => {});
    }
  }, [latest, threadId]);
  async function createThread() {
    try { const created = await post<Thread>("/threads", { event_id: event, title: `${event} · 事件研究` }); router.push(`/workspace/chats/${created.thread_id}`); }
    catch (e) { setError((e as Error).message); }
  }
  async function send(execute: boolean) {
    if (!threadId) return;
    try {
      setError(""); setBusy(true);
      if(requestDirty) throw new Error("阶段或输入已更改，请先点击‘将阶段与参数写入运行配置’，再提交。");
      const request = requestText.trim() ? JSON.parse(requestText) : null;
      const result = await post<{ execution_id: string }>(`/threads/${threadId}/runs`, { message: message || (execute ? "执行所选运行配置" : "生成事件研究计划"), request, execute });
      setExecution(result.execution_id);
    } catch (e) { setError((e as Error).message); setBusy(false); }
  }
  async function upload(file?: File) {
    if (!file || !threadId) return;
    try {
      const records = JSON.parse(await file.text());
      const result = await post<Dataset>(`/threads/${threadId}/datasets`, { records });
      setDataset(result.dataset_id); setDatasets(await api(`/threads/${threadId}/datasets`));
    } catch (e) { setError((e as Error).message); }
  }
  return <div className="shell">
    <aside className="sidebar"><Link href="/workspace" className="brand"><span className="brand-mark">T</span><div>Tweets2Insights<small>RESEARCH WORKSPACE</small></div></Link>
      <div className="new-thread"><label>事件 ID<input value={event} onChange={(e) => setEvent(e.target.value)} placeholder="event-id" /></label><button className="primary" onClick={createThread}>＋ 新建会话</button></div>
      <div className="sidebar-label">研究会话</div><nav>{threads.map((t) => <Link className={t.thread_id === threadId ? "active" : ""} href={`/workspace/chats/${t.thread_id}`} key={t.thread_id}>{t.title}<small>{t.event_id}</small></Link>)}</nav>
      <footer><span className="status-dot" /> 本地研究环境<br /><small>模型标注自动执行 · Demo 独立评测</small></footer>
    </aside>
    <main className="main"><header><div><p className="eyebrow">EVENT INTELLIGENCE</p><h1>{thread?.title ?? "从一场事件，开始研究"}</h1></div><span className="connection">{connected ? "● 实时连接" : threadId ? "○ 正在连接" : "研究工作台"}</span></header>
      {error && <div className="error" role="alert">{error}</div>}
      {!threadId ? <section className="welcome"><span className="large-mark">↗</span><h2>数据、证据与推演，在同一个工作区。</h2><p>创建事件会话，上传已有数据，或描述需要采集的事件。主 Agent 组织计划，领域服务执行计算。</p><div className="feature-row"><article><b>01 / 复盘</b><p>分布与覆盖率，连接到原始证据。</p></article><article><b>02 / 预测</b><p>显式记录模型、截止点与验证状态。</p></article><article><b>03 / 情景</b><p>相同起点下的条件分支比较。</p></article></div></section> : <div className="work-grid"><section className="conversation"><div className="section-heading"><h2>Leader Agent</h2><span>计划 · 协作 · 委派</span></div>
        <div className="messages">{thread?.messages?.length ? thread.messages.map((m, i) => <article key={i} className={`message ${m.role}`}><small>{m.role === "user" ? "你" : "Leader"}</small><p>{m.content}</p></article>) : <p className="empty">描述事件、时间范围、搜索引擎和希望得到的结果。也可直接使用右侧结构化配置。</p>}
          {latest?.node && <div className="progress-note">当前阶段：{latest.node} · {latest.status ?? "处理中"}</div>}
        </div><div className="composer"><textarea value={message} onChange={(e) => setMessage(e.target.value)} placeholder="例如：基于上传数据，复盘公众情绪与立场变化。使用 Tavily 搜索，分析最近七天。" rows={4} /><div className="actions"><button disabled={busy} onClick={() => send(false)}>生成计划</button><button disabled={busy} className="primary" onClick={() => send(true)}>提交执行</button>{busy && execution && <button onClick={() => post(`/threads/${threadId}/runs/${execution}/cancel`, {}).catch((e: Error) => setError(e.message))}>停止 Agent</button>}</div></div>
        <JobPanel threadId={threadId} />
      </section><aside className="context-panel"><h2>事件与输入</h2><p className="caption">上传或选择已有数据时，不启动采集。</p><label className="upload">上传标准 JSON<input type="file" accept=".json" onChange={(e) => upload(e.target.files?.[0])} /></label>
        <label>数据版本<select value={dataset} onChange={(e) => {setDataset(e.target.value);setRequestDirty(true);}}><option value="">选择数据</option>{datasets.map((d) => <option key={d.dataset_id} value={d.dataset_id}>{d.dataset_id.slice(0, 18)}… · {d.count} 条</option>)}</select></label>
        <label>唯一搜索引擎<select value={provider} onChange={(e) => {setProvider(e.target.value);setRequestDirty(true);}}><option value="tavily">Tavily</option><option value="deepseek">DeepSeek Search</option></select></label>
        <label>事件关键词<input value={keywords} onChange={(e) => {setKeywords(e.target.value);setRequestDirty(true);}} placeholder="多个关键词以逗号分隔" /></label>
        {thread&&<WorkflowBuilder key={threadId} eventId={thread.event_id} dataset={dataset} keywords={keywords} searchProvider={provider} onDirty={()=>setRequestDirty(true)} onBuild={text=>{setRequestText(text);setRequestDirty(false);}}/>}
        {requestDirty&&<p className="caption">表单更改尚未写入运行配置。</p>}
        <ProviderSettings/>
        <details open><summary>运行配置 · 可编辑</summary><textarea className="request-editor" value={requestText} onChange={(e) => {setRequestText(e.target.value);setRequestDirty(false);}} spellCheck={false} rows={18} placeholder="可在此加入采集、预测或情景参数；也可留空，由 Leader 生成。" /><button onClick={() => {setRequestText("");setRequestDirty(false);}}>清空配置，重新由 Agent 规划</button></details>
        <p className="caption">预测与情景属于实验性模型结果。程序不会将未知字段填为中性，也不会把预设质量阈值写成已验证成绩。</p>
      </aside></div>}
    </main>
  </div>;
}
