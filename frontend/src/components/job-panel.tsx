"use client";
import { useI18n } from "./language-provider";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  Download,
  FileChartColumn,
  Play,
  RotateCcw,
  Search,
  Square,
} from "lucide-react";
import { artifactLabels } from "@/lib/i18n";
import { api, post } from "@/lib/api";
import type { Job, DomainResult, ArtifactRef } from "@/lib/types";
import { ArtifactViewer } from "./artifact-viewer";
import { Card } from "./tremor/Card";
import { Badge } from "./tremor/Badge";
import { EmptyState, StatusBadge, statusLabels } from "./ui";

export function JobPanel({
  threadId,
  jobs,
  onRefresh,
  active,
}: {
  threadId: string;
  jobs: Job[];
  onRefresh: () => void;
  active: boolean;
}) {
  const { t, locale } = useI18n();
  const [selected, setSelected] = useState("");
  const [result, setResult] = useState<DomainResult>({});
  const [artifact, setArtifact] = useState<ArtifactRef>();
  const [error, setError] = useState("");
  const [pending, setPending] = useState("");
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [tools, setTools] = useState<{ name: string; description: string }[]>(
    [],
  );
  const [tool, setTool] = useState("sentiment_time_series");
  const [parameters, setParameters] = useState("{}");
  const selectedStatus = jobs.find((job) => job.job_id === selected)?.status;
  useEffect(() => {
    api<{ name: string; description: string }[]>("/analysis-tools")
      .then(setTools)
      .catch((e: Error) => setError(e.message));
  }, []);
  useEffect(() => {
    setSelected("");
    setResult({});
    setArtifact(undefined);
    setError("");
  }, [threadId]);
  useEffect(() => {
    if (!selected) return;
    let live = true;
    setLoading(true);
    setError("");
    setResult({});
    setArtifact(undefined);
    api<DomainResult>(`/threads/${threadId}/jobs/${selected}/result`)
      .then((data) => {
        if (live) {
          setResult(data);
          setArtifact(
            data.artifacts?.report ??
              data.artifacts?.charts ??
              Object.values(data.artifacts ?? {})[0],
          );
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
  }, [selected, selectedStatus, threadId]);
  async function action(job: Job, name: string) {
    setPending(job.job_id);
    setError("");
    try {
      await post(`/threads/${threadId}/jobs/${job.job_id}/${name}`, {});
      onRefresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending("");
    }
  }
  async function supplement() {
    setPending("supplement");
    setError("");
    try {
      await post(
        `/threads/${threadId}/jobs/${selected}/analysis-tools/${tool}`,
        JSON.parse(parameters),
      );
      onRefresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending("");
    }
  }
  const visible = jobs.filter(
    (job) =>
      (filter === "all" ||
        (filter === "active"
          ? [
              "queued",
              "running",
              "waiting_for_auth",
              "cancel_requested",
            ].includes(job.status)
          : job.status === filter)) &&
      `${job.run_id} ${job.stage}`.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <div className="results-layout">
      <Card className="surface section-card">
        <div className="section-heading">
          <div>
            <h2>
              {t("研究任务")}
              <Badge variant="neutral">{jobs.length}</Badge>
            </h2>
            <p className="muted">{t("追踪执行阶段，查看分析结果与报告。")}</p>
          </div>
          <div className="search-field">
            <Search size={16} />
            <input
              aria-label={t("搜索研究任务")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("搜索任务…")}
            />
          </div>
        </div>
        <div className="filterbar" aria-label={t("任务状态筛选")}>
          {[
            ["all", t("全部任务")],
            ["active", t("进行中")],
            ["completed", t("已完成")],
            ["failed", t("失败")],
            ["partial", t("部分完成")],
          ].map(([key, label]) => (
            <button
              key={key}
              aria-pressed={filter === key}
              className={filter === key ? "selected" : ""}
              onClick={() => setFilter(key)}
            >
              {label}
            </button>
          ))}
        </div>
        {error && (
          <p className="error" role="alert">
            {t(error)}
          </p>
        )}
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{t("任务")}</th>
                <th>{t("当前阶段")}</th>
                <th>{t("状态")}</th>
                <th>{t("操作")}</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((job) => (
                <tr
                  key={job.job_id}
                  className={selected === job.job_id ? "selected-row" : ""}
                >
                  <td>
                    <strong>{job.run_id}</strong>
                    {job.error_type && (
                      <small className="cell-error">{job.error_type}</small>
                    )}
                  </td>
                  <td className="muted">
                    {t(
                      artifactLabels[job.stage] ??
                        statusLabels[job.stage] ??
                        job.stage ??
                        "等待执行",
                    ) || t("等待执行")}
                  </td>
                  <td>
                    <StatusBadge status={job.status} />
                  </td>
                  <td>
                    <div className="actions">
                      {["queued", "running", "waiting_for_auth"].includes(
                        job.status,
                      ) && (
                        <button
                          disabled={!!pending}
                          onClick={() => action(job, "cancel")}
                        >
                          <Square size={13} />
                          {t("取消")}
                        </button>
                      )}
                      {["partial", "failed", "cancelled"].includes(
                        job.status,
                      ) && (
                        <button
                          disabled={!!pending}
                          onClick={() => action(job, "retry")}
                        >
                          <RotateCcw size={13} />
                          {t("重试")}
                        </button>
                      )}
                      {job.status === "waiting_for_auth" && (
                        <button
                          disabled={!!pending}
                          onClick={() => action(job, "resume")}
                        >
                          <Play size={13} />
                          {t("恢复")}
                        </button>
                      )}
                      {["completed", "partial"].includes(job.status) && (
                        <button
                          className="text-link"
                          onClick={() => setSelected(job.job_id)}
                        >
                          {t("查看结果")}
                          <ArrowRight size={14} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!visible.length && (
            <EmptyState
              title={
                jobs.length ? t("没有匹配的任务") : t("等待第一项研究结果")
              }
              description={
                jobs.length
                  ? t("调整状态筛选或搜索关键词。")
                  : t("在研究工作台配置阶段并开始执行，任务会自动出现在这里。")
              }
            />
          )}
        </div>
      </Card>
      {loading && (
        <Card className="surface">
          <p className="loading-text">{t("正在读取研究产物…")}</p>
        </Card>
      )}
      {result.artifacts && (
        <Card className="surface result-card">
          <div className="section-heading">
            <h2>
              <FileChartColumn size={18} />
              {t("研究产物")}
            </h2>
            <span className="muted">
              {t("{count} 项", { count: Object.keys(result.artifacts).length })}
            </span>
          </div>
          <div className="artifact-tabs" aria-label={t("选择研究产物")}>
            {Object.entries(result.artifacts).map(([key, ref]) => (
              <button
                key={key}
                className={
                  artifact?.artifact_id === ref.artifact_id ? "selected" : ""
                }
                aria-pressed={artifact?.artifact_id === ref.artifact_id}
                onClick={() => setArtifact(ref)}
              >
                {t(artifactLabels[key] ?? key)}
              </button>
            ))}
          </div>
          {artifact && active && (
            <ArtifactViewer
              key={`${artifact.run_id}-${artifact.artifact_id}`}
              threadId={threadId}
              reference={artifact}
            />
          )}
          {result.artifacts.labels && (
            <details className="advanced-settings">
              <summary>{t("补充分析")}</summary>
              <p className="caption">
                {t("使用本次标注数据运行其他分析工具，结果保存为新任务。")}
              </p>
              <label>
                {t("分析工具")}
                <select value={tool} onChange={(e) => setTool(e.target.value)}>
                  {tools.map((item) => (
                    <option key={item.name} value={item.name}>
                      {locale === "en-US"
                        ? item.name.replaceAll("_", " ")
                        : item.description}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t("工具参数（JSON）")}
                <textarea
                  value={parameters}
                  onChange={(e) => setParameters(e.target.value)}
                />
              </label>
              <button disabled={!!pending} onClick={supplement}>
                <Download size={15} />
                {t("提交补充分析")}
              </button>
            </details>
          )}
        </Card>
      )}
    </div>
  );
}
