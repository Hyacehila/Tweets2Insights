"use client";

import { Component, createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { createLibrary, defineComponent, Renderer, type OpenUIError } from "@openuidev/react-lang";
import { ArrowRight, ChartNoAxesCombined, ChevronDown, Maximize2, Minimize2, MessageSquareText, RotateCcw, Send, SlidersHorizontal, Sparkles, Square, X } from "lucide-react";
import { api, post } from "@/lib/api";
import { componentSpecs, starterProgram } from "@/lib/openui-schema.mjs";
import { consumeUIStream } from "@/lib/ui-stream.mjs";
import type { CanvasPage, DataFilters, IntelligenceContext, Simulation, UIMessage, WorkspaceView } from "@/lib/intelligence-types";
import { useI18n } from "./language-provider";
import { AnalysisChart } from "./analysis-chart";
import { EmptyState, formatDate } from "./ui";

type Binding = { threadId?: string; data?: IntelligenceContext; filters: DataFilters; setFilters: (filters: DataFilters) => void; loading: boolean; error: string; navigate: (page: CanvasPage) => void; refresh: () => void };
const BindingContext = createContext<Binding | null>(null);
function useBinding() { const value = useContext(BindingContext); if (!value) throw new Error("Research data provider missing"); return value; }

export function IntelligenceProvider({ threadId, datasetId, refreshKey, navigate, children }: { threadId?: string; datasetId?: string; refreshKey: number; navigate: Binding["navigate"]; children: ReactNode }) {
  const [filters, updateFilters] = useState<DataFilters>({});
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(`t2i-filters:${threadId}`) || "{}");
      const clean = Object.fromEntries(Object.entries(saved).filter(([key, value]) => ["dataset_id", "start", "end", "platform"].includes(key) && typeof value === "string"));
      updateFilters(clean);
    } catch { updateFilters({}); }
  }, [threadId]);
  const setFilters = useCallback((value: DataFilters) => {
    updateFilters(value);
    try { localStorage.setItem(`t2i-filters:${threadId}`, JSON.stringify(value)); } catch { /* Filtering still works without browser storage. */ }
  }, [threadId]);
  const [data, setData] = useState<IntelligenceContext>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision(value => value + 1), []);
  useEffect(() => { if (datasetId) updateFilters(old => ({ ...old, dataset_id: datasetId })); }, [datasetId]);
  useEffect(() => { if (!threadId) return; const timer = setInterval(refresh, 15000); return () => clearInterval(timer); }, [threadId, refresh]);
  useEffect(() => {
    if (!threadId) return;
    let live = true;
    const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => !!value));
    setLoading(true); setError("");
    api<IntelligenceContext>(`/threads/${threadId}/intelligence/context?${query}`).then(value => { if (live) setData(value); }).catch(e => { if (live) { setError(e.message); setData(undefined); } }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [threadId, filters, refreshKey, revision]);
  return <BindingContext.Provider value={{ threadId, data, filters, setFilters, loading, error, navigate, refresh }}>{children}</BindingContext.Provider>;
}

function FilterControls() {
  const { t } = useI18n();
  const { data, filters, setFilters, loading, error } = useBinding();
  const [draft, setDraft] = useState(filters);
  useEffect(() => setDraft(filters), [filters]);
  return <form className="canvas-filters" onSubmit={e => { e.preventDefault(); setFilters(draft); }}>
    <div className="canvas-filter-title"><SlidersHorizontal size={15}/>{t("筛选数据")}</div>
    <div className="canvas-filter-inputs">
      <label>{t("开始日期")}<input type="date" value={draft.start || ""} max={draft.end || undefined} onChange={e => setDraft({ ...draft, start: e.target.value })}/></label>
      <label>{t("结束日期")}<input type="date" value={draft.end || ""} min={draft.start || undefined} onChange={e => setDraft({ ...draft, end: e.target.value })}/></label>
      <label>{t("平台")}<select value={draft.platform || ""} onChange={e => setDraft({ ...draft, platform: e.target.value })}><option value="">{t("全部平台")}</option>{data?.platforms.map(platform => <option key={platform}>{platform}</option>)}</select></label>
    </div>
    <div className="actions"><button type="submit" disabled={loading}>{t(loading ? "正在读取…" : "应用筛选")}</button><button type="button" className="text-link" onClick={() => { setDraft({}); setFilters({}); }}>{t("重置")}</button><span className="muted">{t("已选 {count} / {total} 条", { count: data?.dataset?.metrics.posts ?? 0, total: data?.total_posts ?? 0 })}</span></div>
    {error && <p className="error" role="alert">{error}</p>}
  </form>;
}

const metricLabels: Record<string, string> = { posts: "帖子数量", images: "配图数量", image_posts: "图文帖子", interactions: "互动总量", authors: "参与作者", days: "覆盖天数" };
function BoundMetric({ name }: { name: string }) {
  const { data, loading } = useBinding(); const { t, locale } = useI18n();
  const value = data?.dataset?.metrics[name];
  return <div className="canvas-metric" aria-busy={loading}><span>{t(metricLabels[name] || name)}</span><strong>{typeof value === "number" ? value.toLocaleString(locale) : "—"}</strong><small>{t("当前筛选范围")}</small></div>;
}
function BoundChart({ source }: { source: string }) {
  const { data, loading } = useBinding(); const { t } = useI18n();
  const chart = data?.charts[source];
  if (!chart) return <p className="canvas-empty">{t(loading ? "正在读取数据统计…" : "当前数据中没有这项图表")}: {source}</p>;
  return <div className="canvas-chart"><span className="canvas-source">{t(source.startsWith("analysis:") ? "分析运行结果" : "当前筛选范围")}{source.startsWith("analysis:") && data?.run_id ? ` · ${data.run_id}` : ""}</span><AnalysisChart name={source} value={{ ...chart, title: t(chart.title || source) }}/></div>;
}
function EvidencePosts() {
  const { data } = useBinding(); const { t, locale } = useI18n();
  return <section className="canvas-evidence"><h3>{t("高互动帖子证据")}</h3>{!data?.dataset?.top_posts.length && <p className="muted">{t("当前筛选范围没有帖子")}</p>}{data?.dataset?.top_posts.slice(0, 5).map(row => <article key={row.post_id}>
    <p>{row.content}</p><div><time>{row.published_at ? formatDate(row.published_at, locale) : t("时间未知")}</time><span>{t("互动 {count}", { count: row.score.toLocaleString(locale) })}</span>{row.source_url && /^https?:\/\//i.test(row.source_url) && <a href={row.source_url} target="_blank" rel="noreferrer noopener">{t("查看原帖")} ↗</a>}</div>
  </article>)}</section>;
}

export function ScenarioWorkbench() {
  const { data, threadId, navigate } = useBinding(); const { t, locale } = useI18n();
  const [jobId, setJobId] = useState("");
  const [horizon, setHorizon] = useState(7);
  const [shift, setShift] = useState(0.1);
  const [dimension, setDimension] = useState("stance");
  const [duration, setDuration] = useState(1);
  const [assumption, setAssumption] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [results, setResults] = useState<Simulation[]>([]);
  useEffect(() => { if (!threadId) return; let live = true; api<Simulation[]>(`/threads/${threadId}/intelligence/simulations`).then(value => { if (live) setResults(value.reverse()); }).catch(e => { if (live) setError(e.message); }); return () => { live = false; }; }, [threadId]);
  async function simulate(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError("");
    try {
      const result = await post<Simulation>(`/threads/${threadId}/intelligence/simulate`, { job_id: jobId || data?.model_runs[0]?.job_id, horizon, dimension, shift, duration, assumption });
      setResults(previous => [result, ...previous].slice(0, 10));
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <section className="scenario-workbench">
    <div className="canvas-section-heading"><div><h2>{t("条件情景实验")}</h2><p>{t("基于已训练模型，对比同一起点下的基线与情景轨迹")}</p></div><span className="model-tag">PCA + HK · {t("实验模型")}</span></div>
    {data && !data.model_runs.length ? <EmptyState title={t("当前事件尚无已训练的预测模型")} description={t("在事件研判工作台选择意见动力学训练与预测，完成后即可调整情景参数。")}
      action={<button onClick={() => navigate("research")}>{t("配置模型训练")}<ArrowRight size={15}/></button>}/> :
    <form onSubmit={simulate} className="scenario-form">
      <label>{t("模型运行版本")}<select value={jobId || data?.model_runs[0]?.job_id || ""} onChange={e => setJobId(e.target.value)} required><option value="" disabled>{t("选择模型")}</option>{data?.model_runs.map(run => <option key={run.job_id} value={run.job_id}>{run.run_id}</option>)}</select></label>
      <div className="field-grid"><label>{t("预测步数")}<input type="number" min={1} max={30} value={horizon} onChange={e => { setHorizon(Number(e.target.value)); setDuration(value => Math.min(value, Number(e.target.value))); }} required/></label><label>{t("影响维度")}<select value={dimension} onChange={e => setDimension(e.target.value)}><option value="stance">{t("立场")}</option><option value="sentiment">{t("情感")}</option></select></label></div>
      <label>{t("条件偏移强度")}<output>{shift.toFixed(2)}</output><input type="range" min={-1} max={1} step={0.05} value={shift} onChange={e => setShift(Number(e.target.value))}/></label>
      <label>{t("持续步数")}<input type="number" min={1} max={horizon} value={duration} onChange={e => setDuration(Number(e.target.value))} required/></label>
      <label>{t("情景假设")}<textarea value={assumption} onChange={e => setAssumption(e.target.value)} required maxLength={1000} rows={2} placeholder={t("描述从第 1 步起施加该偏移所代表的条件")}/></label>
      <button className="primary" disabled={busy || !data?.model_runs.length}><ChartNoAxesCombined size={16}/>{t(busy ? "正在计算情景…" : "运行情景比较")}</button>
    </form>}
    {error && <p className="error" role="alert">{error}</p>}
    {results.length > 0 && <div className="scenario-results"><h3>{t("情景比较结果")}</h3><p className="muted">{t("条件模拟结果表示模型假设下的差异")}</p>{results.slice(0, 3).map((result, index) => <details key={result.artifact.artifact_id} open={index === 0}>
      <summary>{result.parameters.assumption} <span className="muted">· {result.parameters.dimension} {result.parameters.shift.toFixed(2)} · {result.parameters.horizon} {t("步")}</span></summary>
      <p className="canvas-source">{result.source_run_id}{result.timestamp ? ` · ${formatDate(result.timestamp, locale)}` : ""}</p><div className="canvas-grid">{Object.entries(result.charts).map(([key, chart]) => <AnalysisChart key={key} name={key} value={{ ...chart, title: t(key === "stance" ? "立场轨迹" : "情感轨迹") }}/>)}</div>
      <a className="text-link" href={`/api/threads/${threadId}/exports/${result.artifact.run_id}/${result.artifact.artifact_id}?format=json`}>{t("下载计算结果")}</a>
    </details>)}</div>}
  </section>;
}

const library = createLibrary({ root: "ResearchView", components: [
  defineComponent({ ...componentSpecs.ResearchView, component: ({ props, renderNode }) => <div className="research-canvas">{renderNode(props.children)}</div> }),
  defineComponent({ ...componentSpecs.Grid, component: ({ props, renderNode }) => <div className="canvas-grid">{renderNode(props.children)}</div> }),
  defineComponent({ ...componentSpecs.Summary, component: ({ props }) => <p className="canvas-summary">{props.text}</p> }),
  defineComponent({ ...componentSpecs.Heading, component: ({ props }) => <h3 className="canvas-heading">{props.text}</h3> }),
  defineComponent({ ...componentSpecs.Metric, component: ({ props }) => <BoundMetric name={props.metric}/> }),
  defineComponent({ ...componentSpecs.Chart, component: ({ props }) => <BoundChart source={props.source}/> }),
  defineComponent({ ...componentSpecs.Filters, component: () => <FilterControls/> }),
  defineComponent({ ...componentSpecs.Evidence, component: () => <EvidencePosts/> }),
  defineComponent({ ...componentSpecs.Scenario, component: () => <ScenarioWorkbench/> }),
  defineComponent({ ...componentSpecs.Navigate, component: function Navigation({ props }) { const { navigate } = useBinding(); return <button className="canvas-navigate" onClick={() => navigate(props.page)}>{props.label}<ArrowRight size={15}/></button>; } }),
] });

class CanvasBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}
function GeneratedCanvas({ content, streaming = false }: { content: string; streaming?: boolean }) {
  const { t } = useI18n(); const [errors, setErrors] = useState<string[]>([]);
  const onError = useCallback((values: OpenUIError[]) => { const next = values.filter(item => item.severity !== "warning").map(item => item.message); setErrors(old => JSON.stringify(old) === JSON.stringify(next) ? old : next); }, []);
  return <CanvasBoundary fallback={<p role="alert" className="error">{t("界面生成失败，请重新生成")}</p>}>
    <Renderer response={content} library={library} isStreaming={streaming} onError={onError} publishObservability={false}/>
    {!streaming && errors.length > 0 && <details className="error"><summary>{t("部分界面未能生成，查看原因")}</summary>{errors.map((error, i) => <p key={i}>{error}</p>)}</details>}
  </CanvasBoundary>;
}

export function ForecastWorkspace() {
  const { data } = useBinding(); const { t } = useI18n();
  const charts = Object.keys(data?.charts ?? {}).filter(key => key.startsWith("analysis:forecast-") || key.startsWith("analysis:scenario-"));
  return <div className="forecast-workspace"><div className="view-intro"><span className="view-kicker">FORECAST & SIMULATION</span><h1>{t("趋势与情景推演")}</h1></div>
    {!!charts.length && <div className="dashboard-chart-grid">{charts.map(key => <BoundChart key={key} source={key}/>)}</div>}
    <ScenarioWorkbench/>
  </div>;
}

export function IntelligentAssistant({ open, onClose, page }: { open: boolean; onClose: () => void; page: WorkspaceView }) {
  const { t, locale } = useI18n(); const { threadId, data, filters, refresh } = useBinding();
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [text, setText] = useState(""); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const [loading, setLoading] = useState(false); const [showData, setShowData] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => { if (!threadId) return; let live = true; setLoading(true); api<UIMessage[]>(`/threads/${threadId}/intelligence/messages`).then(value => { if (live) setMessages(value); }).catch(e => { if (live) setError(e.message); }).finally(() => { if (live) setLoading(false); }); return () => { live = false; abort.current?.abort(); }; }, [threadId]);
  useEffect(() => { if (open) bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages.length, busy, open]);
  async function send(prompt = text) {
    if (!threadId || busy || !prompt.trim()) return;
    const content = prompt.trim(), id = Date.now();
    setText(""); setError(""); setBusy(true);
    setMessages(old => [...old, { id, role: "user", content, status: "completed" }, { id: id + 1, role: "assistant", content: "", status: "streaming" }]);
    const controller = new AbortController(); abort.current = controller;
    let terminal = false;
    try {
      const response = await fetch(`/api/threads/${threadId}/intelligence/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: content, locale, page, filters }), signal: controller.signal });
      if (!response.ok) { const value = await response.json().catch(() => ({})); throw new Error(typeof value.detail === "string" ? value.detail : `HTTP ${response.status}`); }
      if (!response.body) throw new Error(t("服务没有返回响应内容"));
      await consumeUIStream(response.body, (kind: string, value: { delta?: string; message?: string; error_type?: string; usage?: Record<string, number> }) => {
        if (kind === "delta") setMessages(old => old.map(row => row.id === id + 1 ? { ...row, content: row.content + value.delta } : row));
        if (kind === "complete" || kind === "error") {
          terminal = true;
          setMessages(old => old.map(row => row.id === id + 1 ? { ...row, status: kind === "complete" ? "completed" : "failed", usage: value.usage, error: kind === "error" ? { message: value.message || "Unknown error", error_type: value.error_type || "Error" } : null } : row));
        }
      });
      if (!terminal) throw new Error(t("连接中断，请重试"));
      setMessages(await api<UIMessage[]>(`/threads/${threadId}/intelligence/messages`));
      refresh();
    } catch (e) {
      const cancelled = controller.signal.aborted;
      setMessages(old => old.map(row => row.id === id + 1 ? { ...row, status: cancelled ? "cancelled" : "failed", error: cancelled ? null : { message: (e as Error).message, error_type: "RequestError" } } : row));
    } finally { setBusy(false); abort.current = null; }
  }
  const starters = ["展示事件的热度变化和高互动帖子", "结合现有分析结果解释主要分歧", "构建一个可调整参数的情景比较界面"];
  return <aside className={`intelligence-panel ${open ? "is-open" : ""} ${expanded ? "is-expanded" : ""}`} aria-label={t("AI 交互分析助手")} hidden={!open}>
    <header><span className="assistant-emblem"><Sparkles size={20}/></span><div><h2>{t("AI 交互分析助手")}</h2><p>OpenUI · {data?.title || t("选择研究事件")}</p></div><button className="icon-button expand-canvas" onClick={() => setExpanded(value => !value)} aria-label={t(expanded ? "收起分析画布" : "展开分析画布")}>{expanded ? <Minimize2 size={16}/> : <Maximize2 size={16}/>}</button><button className="icon-button" onClick={onClose} aria-label={t("关闭分析助手")}><X size={18}/></button></header>
    <div className="assistant-scroll">
      {!threadId && <EmptyState title={t("选择研究事件")} description={t("助手将使用当前事件的数据、分析结果和模型")}/>}
      {threadId && <><div className="assistant-context"><span className="context-dot"/>{t("已连接事件数据")}<button className="text-link" onClick={() => setShowData(value => !value)}>{t("交互数据视图")}<ChevronDown size={14}/></button></div>
        {showData && open && <GeneratedCanvas content={starterProgram(locale)}/>}
        {loading && <p className="muted">{t("正在读取对话…")}</p>}
        {!messages.length && !loading && <div className="assistant-welcome"><Sparkles size={30}/><h3>{t("从一个问题开始探索")}</h3><p>{t("把问题变成可筛选的图表、证据和情景实验")}</p><div className="assistant-starters">{starters.map(prompt => <button key={prompt} disabled={busy} onClick={() => send(t(prompt))}><MessageSquareText size={16}/><span>{t(prompt)}</span><ArrowRight size={14}/></button>)}</div></div>}
        {messages.map((message, index) => <article className={`intelligent-message ${message.role}`} key={message.id}>
          <div className="intelligent-message-role">{message.role === "user" ? t("你") : <><Sparkles size={13}/>{t("分析助手")}</>}</div>
          {message.role === "user" ? <p>{message.content}</p> : <>
            {message.filters && <span className="canvas-source">{t("解读生成时的数据范围")} · {message.filters.start || t("不限起始日期")} → {message.filters.end || t("不限结束日期")} · {message.filters.platform || t("全部平台")}</span>}
            {message.filters && ["start", "end", "platform", "dataset_id"].some(key => (message.filters?.[key as keyof DataFilters] || "") !== (filters[key as keyof DataFilters] || "")) && <p className="canvas-scope-note">{t("筛选已变化，图表已更新；重新生成可更新解读")}</p>}
            {message.content && open ? <GeneratedCanvas content={message.content} streaming={message.status === "streaming"}/> : message.status === "streaming" ? <p className="assistant-thinking"><span className="pulse-dot"/>{t("正在读取证据并组织界面…")}</p> : null}
            {message.error && <div role="alert" className="error"><strong>{message.error.error_type}</strong><p>{message.error.message}</p></div>}
            {message.status === "cancelled" && <p className="muted">{t("已停止生成")}</p>}
            {!!message.usage && Object.keys(message.usage).length > 0 && <span className="canvas-source">{t("本次用量")} · {message.usage.prompt_tokens ?? "—"} + {message.usage.completion_tokens ?? "—"} tokens</span>}
            {message.status !== "streaming" && <button className="text-link regenerate" disabled={busy} onClick={() => send(messages[index - 1]?.content || "") }><RotateCcw size={12}/>{t("重新生成")}</button>}
          </>}
        </article>)}
      </>}
      {error && <p className="error" role="alert">{error}</p>}<div ref={bottom}/>
    </div>
    <form className="assistant-composer" onSubmit={e => { e.preventDefault(); void send(); }}><textarea value={text} onChange={e => setText(e.target.value)} disabled={!threadId} rows={2} maxLength={8000} placeholder={t("询问当前事件，或描述想要的分析界面…")} aria-label={t("分析助手问题")}/><div><span>{t("围绕当前事件持续分析")}</span>{busy ? <button type="button" onClick={() => abort.current?.abort()}><Square size={14}/>{t("停止")}</button> : <button className="primary" disabled={!threadId || !text.trim()} aria-label={t("发送分析问题")}><Send size={16}/></button>}</div></form>
  </aside>;
}
