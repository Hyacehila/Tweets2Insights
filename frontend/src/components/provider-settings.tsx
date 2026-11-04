"use client";
import { useI18n } from "./language-provider";
import { useEffect, useState } from "react";
import { Check, KeyRound, RefreshCw, Save } from "lucide-react";
import { api, post } from "@/lib/api";
import { Card } from "./tremor/Card";
import { Badge } from "./tremor/Badge";
import { AgentModelSettings } from "./agent-model-settings";
import { CrawlerSettings } from "./crawler-settings";

const providers = [
  { id: "agent", name: "Agent 模型", purpose: "规划、分析与报告", mark: "AI" },
  { id: "openai_decisions", name: "OpenAI Decisions", purpose: "默认决策标注 · gpt-6-luna", mark: "O" },
  { id: "jev", name: "TypeSafe Jev", purpose: "舆情数据决策标注", mark: "J" },
  {
    id: "aliyun_decision",
    name: "阿里 Decision",
    purpose: "舆情数据决策标注",
    mark: "A",
  },
  { id: "tavily", name: "Tavily", purpose: "事件检索与外部补证", mark: "T" },
  { id: "deepseek", name: "DeepSeek", purpose: "事件搜索服务", mark: "D" },
  { id: "mediacrawler", name: "MediaCrawler", purpose: "平台登录与关键词采集", mark: "MC" },
];
type ProviderState = { provider: string; configured: boolean };
export function ProviderSettings() {
  const { t } = useI18n();
  const [selected, setSelected] = useState("agent");
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [states, setStates] = useState<ProviderState[]>([]);
  const [apiKey, setApiKey] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const provider = providers.find((item) => item.id === selected)!;
  async function refresh() {
    setLoading(true);
    try {
      const [providers, agent] = await Promise.all([
        api<ProviderState[]>("/providers"),
        api<{ configured: boolean }>("/agent-model"),
      ]);
      setStates([...providers, { provider: "agent", configured: agent.configured }]);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void refresh();
  }, []);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setNotice("");
    setError("");
    try {
      await post("/providers", {
        provider: selected,
        api_key: apiKey.trim(),
        endpoint: selected === "aliyun_decision" ? endpoint.trim() : null,
      });
      setApiKey("");
      setNotice(provider.name);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="provider-layout">
      <Card className="surface provider-list">
        <div className="section-heading">
          <h2>{t("服务供应商")}</h2>
          <button
            className="icon-button"
            onClick={() => { void refresh(); setRefreshVersion((value) => value + 1); }}
            aria-label={t("刷新 API 配置状态")}
          >
            <RefreshCw size={15} />
          </button>
        </div>
        {providers.map((item) => (
          <button
            className={`provider-item ${selected === item.id ? "selected" : ""}`}
            key={item.id}
            disabled={busy}
            onClick={() => {
              setSelected(item.id);
              setApiKey("");
              setEndpoint("");
              setNotice("");
              setError("");
            }}
          >
            <span className="provider-mark">{item.mark}</span>
            <span>
              <strong>{t(item.name)}</strong>
              <small>{t(item.purpose)}</small>
            </span>
            {states.find((state) => state.provider === item.id)?.configured && (
              <Check size={16} className="configured-icon" />
            )}
          </button>
        ))}
      </Card>
      {selected === "agent" ? <AgentModelSettings key={refreshVersion} onConfigured={() => void refresh()} /> : selected === "mediacrawler" ? <CrawlerSettings key={refreshVersion} /> : <Card className="surface provider-form">
        <div className="section-heading">
          <div className="agent-heading">
            <span className="settings-key">
              <KeyRound size={22} />
            </span>
            <div>
              <h2>{t(provider.name)}</h2>
              <p className="muted">{t(provider.purpose)}</p>
            </div>
          </div>
          <Badge
            variant={
              states.find((item) => item.provider === selected)?.configured
                ? "success"
                : "neutral"
            }
          >
            {loading
              ? t("读取中")
              : states.find((item) => item.provider === selected)?.configured
                ? t("已配置")
                : t("待配置")}
          </Badge>
        </div>
        <form onSubmit={save}>
          <label>
            API Key
            <input
              type="password"
              required
              autoComplete="new-password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={t("输入服务商提供的 API Key")}
              disabled={busy}
            />
            <small>{t("保存后输入框会清空；再次配置时输入新密钥。")}</small>
          </label>
          {selected === "aliyun_decision" && (
            <label>
              {t("业务空间接口地址")}
              <input
                type="url"
                required
                value={endpoint}
                onChange={(e) => setEndpoint(e.target.value)}
                placeholder={t(
                  "https://空间ID.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/systemone",
                )}
                disabled={busy}
              />
            </label>
          )}
          <div className="settings-description">
            <h3>{t("如何使用")}</h3>
            <p>
              {selected === "openai_decisions"
                ? t("使用 OpenAI Decisions 原生接口完成话题、发布者、情绪、情感与立场标注，返回类别概率；默认模型为 gpt-6-luna。")
                : selected === "jev" || selected === "aliyun_decision"
                  ? t(
                      "在研究工作台的“标注模型”中选择此服务，即可用于自动标注。",
                    )
                  : t(
                        "在研究工作台的“搜索服务”中选择此供应商，用于事件检索与分析补证。",
                      )}
            </p>
            <p>{t("配置保存在当前电脑，供本地研究任务使用。")}</p>
            {selected === "openai_decisions" && <p><a href="https://developers.openai.com/api/docs/guides/decisions" target="_blank" rel="noreferrer">{t("OpenAI Decisions 官方说明")}</a></p>}
          </div>
          {error && (
            <p className="error" role="alert">
              {t(error)}
            </p>
          )}
          {notice && (
            <p className="success-text" role="status">
              <Check size={16} />
              {t("{provider} 配置已保存，后续任务将使用该凭据。", {
                provider: t(notice),
              })}
            </p>
          )}
          <button
            className="primary"
            type="submit"
            disabled={busy || !apiKey.trim()}
          >
            <Save size={16} />
            {busy ? t("正在保存…") : t("保存配置")}
          </button>
        </form>
      </Card>}
    </div>
  );
}
