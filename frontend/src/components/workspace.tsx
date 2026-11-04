"use client";
import { useI18n } from "./language-provider";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import {
  Activity,
  ArrowRight,
  BarChart3,
  Check,
  ChevronRight,
  Database,
  FileChartColumn,
  FlaskConical,
  FolderOpen,
  LayoutDashboard,
  Languages,
  Menu,
  MessageSquare,
  Moon,
  Plus,
  RefreshCw,
  Search,
  Send,
  Settings2,
  Square,
  Sun,
  UploadCloud,
  X,
} from "lucide-react";
import { artifactLabels } from "@/lib/i18n";
import { api, post } from "@/lib/api";
import { importDatasetFiles } from "@/lib/dataset-import";
import type { Thread, Dataset, Job } from "@/lib/types";
import { useThreadStream } from "@/hooks/use-thread-stream";
import { JobPanel } from "./job-panel";
import { WorkflowBuilder } from "./workflow-builder";
import { ProviderSettings } from "./provider-settings";
import { RecentResearch } from "./recent-research";
import { AppliedMediaNotice } from "./media-input-notice";
import { Card } from "./tremor/Card";
import { Badge } from "./tremor/Badge";
import { EmptyState, Modal, StatusBadge, statusLabels, formatDate } from "./ui";

type View = "overview" | "research" | "datasets" | "results" | "settings";
const views = [
  { id: "overview" as const, label: "研究概览", icon: LayoutDashboard },
  { id: "research" as const, label: "研究工作台", icon: MessageSquare },
  { id: "datasets" as const, label: "数据集", icon: Database },
  { id: "results" as const, label: "分析与报告", icon: FileChartColumn },
  { id: "settings" as const, label: "API 设置", icon: Settings2 },
];

export function Workspace({ threadId }: { threadId?: string }) {
  const { t, locale, toggleLocale } = useI18n();
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [view, setView] = useState<View>(threadId ? "research" : "overview");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [event, setEvent] = useState("");
  const [title, setTitle] = useState("");
  const [createError, setCreateError] = useState("");
  const [search, setSearch] = useState("");
  const [threads, setThreads] = useState<Thread[]>([]);
  const [thread, setThread] = useState<Thread>();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [dataset, setDataset] = useState("");
  const [provider, setProvider] = useState("tavily");
  const [keywords, setKeywords] = useState("");
  const [message, setMessage] = useState("");
  const [requestText, setRequestText] = useState("");
  const [requestDirty, setRequestDirty] = useState(false);
  const [execution, setExecution] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [importedCount, setImportedCount] = useState<number | null>(null);
  const uploadNotice =
    importedCount === null
      ? ""
      : t("已导入 {count} 条记录", {
          count: importedCount.toLocaleString(locale),
        });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dataSearch, setDataSearch] = useState("");
  const { updates, connected } = useThreadStream(threadId);
  const latest = updates.at(-1);
  useEffect(() => setMounted(true), []);
  useEffect(() => {
    let live = true;
    setLoading(true);
    api<Thread[]>("/threads")
      .then((items) => {
        if (live) {
          setThreads(items);
          setError("");
        }
      })
      .catch((e: Error) => {
        if (live) setError(e.message);
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [threadId, refreshKey]);
  useEffect(() => {
    setThread(undefined);
    setDatasets([]);
    setJobs([]);
    setDataset("");
    setKeywords("");
    setProvider("tavily");
    setMessage("");
    setBusy(false);
    setRequestText("");
    setRequestDirty(false);
    setError("");
    setExecution("");
    setImportedCount(null);
    setView(threadId ? "research" : "overview");
    if (!threadId) return;
    let live = true;
    api<Thread>(`/threads/${threadId}`)
      .then((value) => {
        if (!live) return;
        setThread(value);
        if (value.latest_execution?.status === "running") {
          setBusy(true);
          setExecution(value.latest_execution.execution_id);
        }
      })
      .catch((e: Error) => {
        if (live) setError(e.message);
      });
    api<{ run_request?: unknown }>(`/threads/${threadId}/state`)
      .then((s) => {
        if (live && s.run_request)
          setRequestText(JSON.stringify(s.run_request, null, 2));
      })
      .catch((e: Error) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [threadId]);
  useEffect(() => {
    if (!threadId) return;
    let live = true;
    const refresh = async () => {
      try {
        const [data, runs] = await Promise.all([
          api<Dataset[]>(`/threads/${threadId}/datasets`),
          api<Job[]>(`/threads/${threadId}/jobs`),
        ]);
        if (live) {
          setDatasets(data);
          setJobs(runs);
        }
      } catch (e) {
        if (live) setError((e as Error).message);
      }
    };
    void refresh();
    const timer = setInterval(refresh, 5000);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [threadId, refreshKey]);
  useEffect(() => {
    if (!latest) return;
    if (latest.run_request) {
      setRequestText(JSON.stringify(latest.run_request, null, 2));
      setRequestDirty(false);
    }
    if (["completed", "failed", "cancelled"].includes(latest.status ?? "")) {
      setBusy(false);
      if (latest.error_type) setError(`运行失败：${latest.error_type}`);
      if (threadId)
        api<Thread>(`/threads/${threadId}`)
          .then(setThread)
          .catch((e: Error) => setError(e.message));
      setRefreshKey((key) => key + 1);
    }
  }, [latest, threadId]);
  const onDirty = useCallback(() => setRequestDirty(true), []);
  const onBuild = useCallback((text: string) => {
    setRequestText(text);
    setRequestDirty(false);
  }, []);
  async function createThread(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setCreateError("");
    try {
      const created = await post<Thread>("/threads", {
        event_id: event.trim(),
        title: title.trim() || t("{event} · 事件研究", { event: event.trim() }),
      });
      setCreateOpen(false);
      router.push(`/workspace/chats/${created.thread_id}`);
    } catch (e) {
      setCreateError((e as Error).message);
    } finally {
      setCreating(false);
    }
  }
  async function send(execute: boolean) {
    if (!threadId || busy) return;
    try {
      setError("");
      if (requestDirty)
        throw new Error("研究参数已更改，请先点击“应用研究配置”。");
      const request = requestText.trim() ? JSON.parse(requestText) : null;
      setBusy(true);
      const text =
        message.trim() ||
        (execute ? t("执行所选研究阶段") : t("生成事件研究计划"));
      const result = await post<{ execution_id: string }>(
        `/threads/${threadId}/runs`,
        { message: text, request, execute },
      );
      setExecution(result.execution_id);
      setMessage("");
      setThread((old) =>
        old
          ? {
              ...old,
              messages: [
                ...(old.messages ?? []),
                { role: "user", content: text },
              ],
            }
          : old,
      );
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }
  async function upload(files: File[]) {
    if (!files.length || !threadId) return;
    setUploading(true);
    setImportedCount(null);
    try {
      const records = await importDatasetFiles(files, async (file) => {
        const result = await api<{ media_ref: string }>(`/threads/${threadId}/datasets/images`, {
          method: "POST", headers: { "Content-Type": file.type || "application/octet-stream" }, body: file,
        });
        return result.media_ref;
      });
      const result = await post<Dataset>(`/threads/${threadId}/datasets`, {
        records,
      });
      setDataset(result.dataset_id);
      setRequestDirty(true);
      setImportedCount(result.count);
      setDatasets(await api(`/threads/${threadId}/datasets`));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
    }
  }
  const filteredThreads = threads.filter((item) =>
    `${item.title} ${item.event_id}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const visibleDatasets = datasets.filter((item) =>
    item.dataset_id.toLowerCase().includes(dataSearch.toLowerCase()),
  );
  const activeJobs = jobs.filter((job) =>
    ["running", "queued", "cancel_requested"].includes(job.status),
  );
  const completeJobs = jobs.filter((job) => job.status === "completed");
  const nav = (id: View) => {
    setView(id);
    setMobileOpen(false);
  };
  const sessionTable = (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>{t("研究事件")}</th>
            <th>{t("事件标识")}</th>
            <th>{t("创建时间")}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {filteredThreads.map((item) => (
            <tr key={item.thread_id}>
              <td>
                <Link
                  className="table-link"
                  href={`/workspace/chats/${item.thread_id}`}
                >
                  <span className="table-icon">
                    <FolderOpen size={16} />
                  </span>
                  {item.title}
                </Link>
              </td>
              <td>
                <code>{item.event_id}</code>
              </td>
              <td className="muted">{formatDate(item.created_at, locale)}</td>
              <td>
                <Link
                  className="text-link"
                  href={`/workspace/chats/${item.thread_id}`}
                >
                  {t("进入")}
                  <ArrowRight size={14} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!filteredThreads.length && !loading && (
        <EmptyState
          title={search ? t("没有匹配的事件") : t("开始你的第一项事件研究")}
          description={
            search
              ? t("试试其他事件名称或标识。")
              : t("输入一个事件名称，随后导入数据或按关键词采集。")
          }
          action={
            !search && (
              <button className="primary" onClick={() => setCreateOpen(true)}>
                <Plus size={16} />
                {t("新建研究")}
              </button>
            )
          }
        />
      )}
      {loading && <p className="loading-text">{t("正在读取研究会话…")}</p>}
    </div>
  );
  const uploadInput = (
    <label className={`upload-zone ${uploading ? "disabled" : ""}`}>
      <UploadCloud size={25} />
      <strong>
        {uploading ? t("正在导入数据…") : t("选择 JSON 数据与配图")}
      </strong>
      <span>{t("选择一个帖子 JSON，可同时选择它引用的 JPG、PNG 或 WebP 图片。")}</span>
      <span>{t("media_refs 填写图片网址或文件名；本地配图按文件名匹配，每张不超过 16 MiB。")}</span>
      <input
        aria-label={t("上传舆情数据")}
        type="file"
        accept=".json,application/json,.jpg,.jpeg,.png,.webp"
        multiple
        disabled={uploading}
        onChange={(e) => {
          void upload(Array.from(e.target.files ?? []));
          e.target.value = "";
        }}
      />
    </label>
  );
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        {t("跳转到主内容")}
      </a>
      {mobileOpen && (
        <button
          className="sidebar-overlay"
          aria-label={t("关闭导航")}
          onClick={() => setMobileOpen(false)}
        />
      )}
      <aside
        id="workspace-navigation"
        className={`app-sidebar ${mobileOpen ? "is-open" : ""}`}
      >
        <Link href="/workspace" className="brand">
          <span className="brand-mark">
            <BarChart3 size={20} />
          </span>
          <span>
            Tweets2Insights<small>{t("舆情研究工作台")}</small>
          </span>
        </Link>
        <button
          className="new-research"
          onClick={() => {
            setCreateOpen(true);
            setMobileOpen(false);
          }}
        >
          <Plus size={16} />
          {t("新建研究")}
          <span>＋</span>
        </button>
        <p className="nav-label">{t("工作空间")}</p>
        <nav className="main-navigation" aria-label={t("主导航")}>
          {views.map(({ id, label, icon: Icon }) => (
            <button
              aria-current={view === id ? "page" : undefined}
              key={id}
              onClick={() => nav(id)}
              className={view === id ? "active" : ""}
            >
              <Icon size={17} />
              {t(label)}
              {id === "results" && activeJobs.length > 0 && (
                <span className="nav-count">{activeJobs.length}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-section-heading">
          <p className="nav-label">{t("最近研究")}</p>
          <span>{threads.length}</span>
        </div>
        <RecentResearch threads={threads} threadId={threadId} onDeleted={(eventId, ids) => {
          setThreads((items) => items.filter((item) => item.event_id !== eventId));
          if (threadId && ids.includes(threadId)) router.replace("/workspace");
          else setRefreshKey((key) => key + 1);
        }} />
      </aside>
      <div className="app-main">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label={t("打开导航")}
              aria-expanded={mobileOpen}
              aria-controls="workspace-navigation"
              onClick={() => setMobileOpen(true)}
            >
              <Menu size={20} />
            </button>
            <span>{t("工作空间")}</span>
            <ChevronRight size={14} />
            <strong>
              {t(views.find((item) => item.id === view)?.label ?? "")}
            </strong>
          </div>
          <div className="topbar-actions">
            <button
              className="language-switch"
              aria-label={t("切换显示语言")}
              title={t("切换显示语言")}
              onClick={toggleLocale}
            >
              <Languages size={16} />
              <span
                lang="zh-CN"
                className={locale === "zh-CN" ? "current" : ""}
              >
                中文
              </span>
              <span className="language-divider">/</span>
              <span lang="en" className={locale === "en-US" ? "current" : ""}>
                EN
              </span>
            </button>
            {threadId && (
              <span className={`live-status ${connected ? "online" : ""}`}>
                <i />
                {connected ? t("实时同步") : t("正在连接")}
              </span>
            )}
            <button
              className="icon-button"
              aria-label={t("刷新数据")}
              onClick={() => setRefreshKey((key) => key + 1)}
            >
              <RefreshCw size={16} />
            </button>
            <button
              className="icon-button"
              aria-label={t("切换明暗主题")}
              onClick={() =>
                setTheme(resolvedTheme === "dark" ? "light" : "dark")
              }
            >
              {mounted && resolvedTheme === "dark" ? (
                <Sun size={18} />
              ) : (
                <Moon size={18} />
              )}
            </button>
          </div>
        </header>
        <main id="main-content" className="page-content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                {thread ? thread.event_id : "TWEETS2INSIGHTS"}
              </div>
              <h1>
                {view === "settings"
                  ? t("模型与 API 设置")
                  : (thread?.title ?? t("研究概览"))}
              </h1>
              <p>
                {view === "settings"
                  ? t("配置分析、标注、搜索与采集服务。")
                  : t("连接事件数据、Agent 协作与研究洞察。")}
              </p>
            </div>
            <button className="primary" onClick={() => setCreateOpen(true)}>
              <Plus size={16} />
              {t("新建研究")}
            </button>
          </div>
          {error && (
            <div className="error" role="alert">
              <span>{t(error)}</span>
              <button
                className="icon-button"
                aria-label={t("关闭提示")}
                onClick={() => setError("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {
            <>
              {view === "settings" && <ProviderSettings />}
              {view === "overview" && (
                <>
                  <div className="metric-grid">
                    {[
                      {
                        title: thread ? t("数据版本") : t("研究会话"),
                        value: loading
                          ? "—"
                          : thread
                            ? datasets.length
                            : threads.length,
                        detail: thread
                          ? t("当前事件的数据集")
                          : t("所有已创建的研究"),
                        icon: FolderOpen,
                      },
                      {
                        title: thread ? t("数据记录") : t("研究事件"),
                        value: loading
                          ? "—"
                          : thread
                            ? datasets
                                .reduce((sum, item) => sum + item.count, 0)
                                .toLocaleString(locale)
                            : new Set(threads.map((item) => item.event_id))
                                .size,
                        detail: thread
                          ? t("各数据版本记录数之和")
                          : t("按事件标识汇总"),
                        icon: Database,
                      },
                      {
                        title: t("进行中任务"),
                        value: thread ? activeJobs.length : "—",
                        detail: thread
                          ? t("排队与正在执行")
                          : t("选择事件后查看"),
                        icon: Activity,
                      },
                      {
                        title: t("已完成任务"),
                        value: thread ? completeJobs.length : "—",
                        detail: thread
                          ? t("结果已保存，可随时查看")
                          : t("选择事件后查看"),
                        icon: Check,
                      },
                    ].map(({ title, value, detail, icon: Icon }) => (
                      <Card className="surface metric-card" key={title}>
                        <div className="metric-label">
                          {title}
                          <Icon size={16} />
                        </div>
                        <div className="metric-value">{value}</div>
                        <p>{detail}</p>
                      </Card>
                    ))}
                  </div>
                  <Card className="surface journey-card">
                    <div>
                      <Badge variant="neutral">{t("研究流程")}</Badge>
                      <h2>{t("从事件数据，到可解释的研究结论")}</h2>
                      <p>
                        {t("按研究目标选择阶段，由 Leader Agent 组织执行。")}
                      </p>
                      <button
                        className="text-link"
                        onClick={() =>
                          threadId ? nav("research") : setCreateOpen(true)
                        }
                      >
                        {t("开始研究")}
                        <ArrowRight size={16} />
                      </button>
                    </div>
                    <div className="journey-steps">
                      {[
                        {
                          icon: Database,
                          name: t("数据与标注"),
                          note: t("上传数据 / 关键词采集"),
                        },
                        {
                          icon: BarChart3,
                          name: t("复盘与预测"),
                          note: t("Agent 分析 / 意见动力学"),
                        },
                        {
                          icon: FileChartColumn,
                          name: t("模拟与报告"),
                          note: t("情景比较 / 结果解读"),
                        },
                      ].map(({ icon: Icon, name, note }, index) => (
                        <div key={name}>
                          <span className="step-icon">
                            <Icon size={20} />
                          </span>
                          <small>0{index + 1}</small>
                          <strong>{name}</strong>
                          <p>{note}</p>
                        </div>
                      ))}
                    </div>
                  </Card>
                  <Card className="surface section-card">
                    <div className="section-heading">
                      <div>
                        <h2>{t("事件研究")}</h2>
                        <p className="muted">
                          {t("继续已有研究，或创建新的事件会话。")}
                        </p>
                      </div>
                      <div className="search-field">
                        <Search size={16} />
                        <input
                          aria-label={t("搜索研究事件")}
                          placeholder={t("搜索事件…")}
                          value={search}
                          onChange={(e) => setSearch(e.target.value)}
                        />
                      </div>
                    </div>
                    {sessionTable}
                  </Card>
                </>
              )}
              {view !== "overview" && view !== "settings" && !threadId && (
                <Card className="surface section-card">
                  <div className="section-heading">
                    <div>
                      <h2>{t("选择一个研究事件")}</h2>
                      <p className="muted">
                        {t("数据、任务和报告按事件组织。")}
                      </p>
                    </div>
                  </div>
                  {sessionTable}
                </Card>
              )}
              {threadId && (
                <>
                  <div hidden={view !== "research"}>
                    <div className="research-tabs">
                      <span className="selected">{t("研究配置与执行")}</span>
                      <button onClick={() => nav("results")}>
                        {t("分析与报告")}
                        {jobs.length > 0 && <span>{jobs.length}</span>}
                      </button>
                      <button onClick={() => nav("datasets")}>
                        {t("输入数据")}
                      </button>
                    </div>
                    <div className="research-grid">
                      <div className="research-settings">
                        <Card className="surface">
                          <div className="section-heading">
                            <h2>
                              <Database size={17} />
                              {t("输入与研究目标")}
                            </h2>
                            <Badge variant="neutral">01</Badge>
                          </div>
                          {uploadInput}
                          {uploadNotice && (
                            <p className="success-text" role="status">
                              {uploadNotice}
                            </p>
                          )}
                          <div className="field-grid">
                            <label>
                              {t("数据版本")}
                              <select
                                value={dataset}
                                onChange={(e) => {
                                  setDataset(e.target.value);
                                  setRequestDirty(true);
                                }}
                              >
                                <option value="">{t("选择已有数据")}</option>
                                {datasets.map((item) => (
                                  <option
                                    key={item.dataset_id}
                                    value={item.dataset_id}
                                  >
                                    {item.dataset_id.slice(0, 14)} ·{" "}
                                    {t("{count} 条", {
                                      count: item.count.toLocaleString(locale),
                                    })}
                                  </option>
                                ))}
                              </select>
                            </label>
                            <label>
                              {t("搜索服务")}
                              <select
                                value={provider}
                                onChange={(e) => {
                                  setProvider(e.target.value);
                                  setRequestDirty(true);
                                }}
                              >
                                <option value="tavily">Tavily</option>
                                <option value="deepseek">
                                  DeepSeek Search
                                </option>
                              </select>
                            </label>
                          </div>
                          <label>
                            {t("事件关键词")}
                            <input
                              value={keywords}
                              onChange={(e) => {
                                setKeywords(e.target.value);
                                setRequestDirty(true);
                              }}
                              placeholder={t("例如：城市暴雨、交通出行")}
                            />
                          </label>
                          {thread && (
                            <WorkflowBuilder
                              key={threadId}
                              eventId={thread.event_id}
                              dataset={dataset}
                              keywords={keywords}
                              searchProvider={provider}
                              onDirty={onDirty}
                              onBuild={onBuild}
                            />
                          )}
                          {requestDirty ? (
                            <p className="warning-text">
                              {t("配置已更改，请应用后执行。")}
                            </p>
                          ) : (
                            requestText && (
                              <p className="success-text">
                                <Check size={14} />
                                {t("研究配置已就绪")}
                              </p>
                            )
                          )}
                          <details className="advanced-settings">
                            <summary>{t("高级运行配置")}</summary>
                            <AppliedMediaNotice requestText={requestText} />
                            <textarea
                              aria-label={t("运行配置 JSON")}
                              className="request-editor"
                              value={requestText}
                              onChange={(e) => {
                                setRequestText(e.target.value);
                                setRequestDirty(false);
                              }}
                              rows={14}
                              spellCheck={false}
                            />
                            <button
                              onClick={() => {
                                setRequestText("");
                                setRequestDirty(false);
                              }}
                            >
                              {t("改用自然语言规划")}
                            </button>
                          </details>
                        </Card>
                      </div>
                      <div className="agent-column">
                        <Card className="surface agent-card">
                          <div className="section-heading">
                            <div className="agent-heading">
                              <span className="agent-avatar">
                                <FlaskConical size={19} />
                              </span>
                              <div>
                                <h2>Leader Agent</h2>
                                <p className="muted">
                                  {t("规划研究，协调分析与结果解读")}
                                </p>
                              </div>
                            </div>
                            <Badge variant={busy ? "default" : "neutral"}>
                              {busy ? t("处理中") : t("准备就绪")}
                            </Badge>
                          </div>
                          <div className="messages" aria-live="polite">
                            {thread?.messages?.length ? (
                              thread.messages.map((item, i) => (
                                <article
                                  key={i}
                                  className={`message ${item.role}`}
                                >
                                  <small>
                                    {item.role === "user"
                                      ? t("你")
                                      : "Leader Agent"}
                                  </small>
                                  <p>{item.content}</p>
                                </article>
                              ))
                            ) : (
                              <EmptyState
                                title={t("这次你想了解什么？")}
                                description={t(
                                  "可以描述事件背景、关注的人群、需要比较的阶段或希望解释的变化。",
                                )}
                              />
                            )}
                            {busy && (
                              <div className="progress-note">
                                <span className="pulse-dot" />
                                {latest?.node
                                  ? t("正在处理：{node}", { node: latest.node })
                                  : t("正在组织研究…")}
                              </div>
                            )}
                          </div>
                          <div className="composer">
                            <textarea
                              aria-label={t("研究需求")}
                              value={message}
                              onChange={(e) => setMessage(e.target.value)}
                              placeholder={t(
                                "描述你想研究的问题，或直接执行左侧配置…",
                              )}
                              rows={3}
                            />
                            <div className="composer-footer">
                              <span>
                                {requestText
                                  ? t("使用已配置的研究参数")
                                  : t("根据自然语言规划")}
                              </span>
                              <div className="actions">
                                <button
                                  disabled={busy}
                                  onClick={() => send(false)}
                                >
                                  {t("生成计划")}
                                </button>
                                <button
                                  disabled={busy || uploading || !thread}
                                  className="primary"
                                  onClick={() => send(true)}
                                >
                                  <Send size={14} />
                                  {t("开始执行")}
                                </button>
                                {busy && execution && (
                                  <button
                                    onClick={() =>
                                      post(
                                        `/threads/${threadId}/runs/${execution}/cancel`,
                                        {},
                                      ).catch((e: Error) => setError(e.message))
                                    }
                                  >
                                    <Square size={13} />
                                    {t("停止")}
                                  </button>
                                )}
                              </div>
                            </div>
                          </div>
                        </Card>
                        <Card className="surface activity-card">
                          <div className="section-heading">
                            <h2>{t("执行动态")}</h2>
                            <button
                              className="text-link"
                              onClick={() => nav("results")}
                            >
                              {t("查看全部")}
                              <ArrowRight size={14} />
                            </button>
                          </div>
                          {jobs.slice(0, 3).map((job) => (
                            <div className="activity-row" key={job.job_id}>
                              <span className="activity-icon">
                                <Activity size={16} />
                              </span>
                              <div>
                                <strong>{job.run_id}</strong>
                                <p>
                                  {t(
                                    artifactLabels[job.stage] ??
                                      statusLabels[job.stage] ??
                                      job.stage ??
                                      "等待执行",
                                  ) || t("等待执行")}
                                </p>
                              </div>
                              <StatusBadge status={job.status} />
                            </div>
                          ))}
                          {!jobs.length && (
                            <p className="muted compact-empty">
                              {t("研究开始后，执行进度会显示在这里。")}
                            </p>
                          )}
                        </Card>
                      </div>
                    </div>
                  </div>
                  {view === "datasets" && (
                    <div className="datasets-grid">
                      <Card className="surface">
                        <h2>{t("导入事件数据")}</h2>
                        <p className="muted">
                          {t("支持标准帖子记录 JSON 数组。")}
                        </p>
                        {uploadInput}
                        {uploadNotice && (
                          <p className="success-text">{uploadNotice}</p>
                        )}
                        <p className="caption">
                          {t(
                            "也可以在研究工作台选择“关键词采集”，按时间范围获取事件数据。",
                          )}
                        </p>
                        <button onClick={() => nav("research")}>
                          {t("配置关键词采集")}
                          <ArrowRight size={15} />
                        </button>
                      </Card>
                      <Card className="surface section-card">
                        <div className="section-heading">
                          <h2>
                            {t("数据版本")}
                            <Badge variant="neutral">{datasets.length}</Badge>
                          </h2>
                          <div className="search-field">
                            <Search size={15} />
                            <input
                              aria-label={t("搜索数据版本")}
                              placeholder={t("搜索版本…")}
                              value={dataSearch}
                              onChange={(e) => setDataSearch(e.target.value)}
                            />
                          </div>
                        </div>
                        <div className="table-scroll">
                          <table>
                            <thead>
                              <tr>
                                <th>{t("数据版本")}</th>
                                <th>{t("记录数")}</th>
                                <th />
                              </tr>
                            </thead>
                            <tbody>
                              {visibleDatasets.map((item) => (
                                <tr key={item.dataset_id}>
                                  <td>
                                    <code className="dataset-id">
                                      {item.dataset_id}
                                    </code>
                                  </td>
                                  <td>{item.count.toLocaleString(locale)}</td>
                                  <td>
                                    <button
                                      className={
                                        dataset === item.dataset_id
                                          ? "selected-button"
                                          : ""
                                      }
                                      onClick={() => {
                                        setDataset(item.dataset_id);
                                        setRequestDirty(true);
                                        nav("research");
                                      }}
                                    >
                                      {dataset === item.dataset_id
                                        ? t("已选择")
                                        : t("用于研究")}
                                    </button>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          {!visibleDatasets.length && (
                            <EmptyState
                              title={
                                dataSearch
                                  ? t("没有匹配的数据版本")
                                  : t("还没有事件数据")
                              }
                              description={t(
                                "导入数据后即可查看版本并用于研究。",
                              )}
                            />
                          )}
                        </div>
                      </Card>
                    </div>
                  )}
                  <div hidden={view !== "results"}>
                    <JobPanel
                      active={view === "results"}
                      threadId={threadId}
                      jobs={jobs}
                      onRefresh={() => setRefreshKey((key) => key + 1)}
                    />
                  </div>
                </>
              )}
            </>
          }
          <footer className="page-footer">
            <span>Tweets2Insights</span>
            <span>{t("事件复盘 · 意见预测 · 情景分析")}</span>
          </footer>
        </main>
      </div>
      <Modal
        open={createOpen}
        onOpenChange={setCreateOpen}
        title={t("新建事件研究")}
        description={t("为这次研究命名，随后配置数据与分析阶段。")}
      >
        <form className="create-form" onSubmit={createThread}>
          <label>
            {t("研究名称")}
            <input
              autoFocus
              required
              maxLength={120}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={t("例如：城市暴雨事件舆情研究")}
            />
          </label>
          <label>
            {t("事件标识")}
            <input
              required
              pattern="[A-Za-z0-9][A-Za-z0-9_.-]{0,127}"
              maxLength={128}
              value={event}
              onChange={(e) => setEvent(e.target.value)}
              placeholder={t("例如：rain-2026")}
            />
            <small>
              {t("使用字母、数字、短横线或下划线；同一标识共享事件数据。")}
            </small>
          </label>
          {createError && (
            <p className="error" role="alert">
              {t(createError)}
            </p>
          )}
          <div className="modal-actions">
            <button type="button" onClick={() => setCreateOpen(false)}>
              {t("取消")}
            </button>
            <button className="primary" type="submit" disabled={creating}>
              {creating ? t("正在创建…") : t("创建研究")}
              <ArrowRight size={15} />
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
