"use client";

import { useEffect, useState } from "react";
import { Check, ExternalLink, KeyRound, Save } from "lucide-react";
import { api, post } from "@/lib/api";
import { useI18n } from "./language-provider";
import { Card } from "./tremor/Card";
import { Badge } from "./tremor/Badge";

type ModelConfig = {
  provider: "qwen" | "glm" | "openai_compatible";
  base_url: string;
  model: string;
  max_tokens: number;
  timeout_seconds: number;
  extra_body: Record<string, unknown>;
};
type Preset = { id: string; name: string; source: string; config: ModelConfig };
type ModelState = { config: ModelConfig; configured: boolean; presets: Preset[] };

export function AgentModelSettings({ onConfigured }: { onConfigured: () => void }) {
  const { t } = useI18n();
  const [saved, setSaved] = useState<ModelState | null>(null);
  const [config, setConfig] = useState<ModelConfig | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [extra, setExtra] = useState("{}");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api<ModelState>("/agent-model")
      .then((value) => {
        if (cancelled) return;
        setSaved(value);
        setConfig(value.config);
        setExtra(JSON.stringify(value.config.extra_body, null, 2));
      })
      .catch((e) => { if (!cancelled) setError((e as Error).message); });
    return () => { cancelled = true; };
  }, []);

  function select(id: string) {
    const preset = saved?.presets.find((item) => item.id === id);
    const next: ModelConfig = preset ? { ...preset.config } : {
      provider: "openai_compatible", base_url: "", model: "",
      max_tokens: 8192, timeout_seconds: 120, extra_body: {},
    };
    setConfig(next);
    setExtra(JSON.stringify(next.extra_body, null, 2));
    setApiKey("");
    setNotice("");
    setError("");
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!config || busy) return;
    setBusy(true);
    setNotice("");
    setError("");
    try {
      let extraBody: Record<string, unknown>;
      try {
        extraBody = JSON.parse(extra);
        if (!extraBody || Array.isArray(extraBody) || typeof extraBody !== "object") throw new Error();
      } catch { throw new Error("附加参数必须是 JSON 对象。"); }
      const result = await post<{ config: ModelConfig; configured: boolean }>("/agent-model", {
        config: { ...config, base_url: config.base_url.trim(), model: config.model.trim(), extra_body: extraBody },
        api_key: apiKey.trim(),
      });
      setConfig(result.config);
      setSaved((previous) => previous && { ...previous, ...result });
      setApiKey("");
      setNotice("接口与 JSON 输出检查通过，配置已保存。后续 Agent 任务将使用此模型。");
      onConfigured();
    } catch (e) {
      setError((e as Error).message);
    } finally { setBusy(false); }
  }

  const configured = !!saved?.configured && saved.config.base_url === config?.base_url.trim().replace(/\/$/, "");
  const changed = config && saved && (JSON.stringify(config) !== JSON.stringify(saved.config) || extra !== JSON.stringify(saved.config.extra_body, null, 2) || !!apiKey);
  return (
    <Card className="surface provider-form agent-model-form">
      <div className="section-heading">
        <div className="agent-heading">
          <span className="settings-key"><KeyRound size={22} /></span>
          <div><h2>{t("Agent 模型")}</h2><p className="muted">{t("规划、分析与报告")}</p></div>
        </div>
        <Badge variant={saved?.configured && !changed ? "success" : "neutral"}>
          {!saved ? t("读取中") : changed ? t("待检测保存") : saved.configured ? t("已配置") : t("待配置")}
        </Badge>
      </div>
      {saved && config && <form onSubmit={save}>
        <fieldset className="model-fields" disabled={busy}>
          <div className="model-presets" aria-label={t("推荐模型")}>
            {saved.presets.map((preset) => <button key={preset.id} type="button"
              className={`model-preset ${config.provider === preset.id ? "active" : ""}`}
              onClick={() => select(preset.id)}>
              <strong>{preset.name}</strong><small>{t(preset.id === "qwen" ? "默认推荐 · 综合分析" : "推荐 · 推理与报告")}</small>
            </button>)}
            <button type="button" className={`model-preset ${config.provider === "openai_compatible" ? "active" : ""}`} onClick={() => select("openai_compatible")}>
              <strong>{t("自定义服务")}</strong><small>{t("OpenAI 兼容接口")}</small>
            </button>
          </div>
          <p className="muted model-scope">{t("Leader、标签设计、分析论坛和报告 Agent 共用此配置；OpenAI Decisions / Jev / 阿里 Decision 弱标注单独配置。")}</p>
          <div className="model-input-grid">
            <label>Base URL<input type="url" required value={config.base_url} placeholder="https://api.example.com/v1"
              onChange={(e) => setConfig({ ...config, base_url: e.target.value })} />
              <small>{t("填写接口基础地址，不含 /chat/completions。")}</small>
            </label>
            <label>Model ID<input required maxLength={160} value={config.model} placeholder={t("服务商提供的模型 ID")}
              onChange={(e) => setConfig({ ...config, model: e.target.value })} />
              <small>{t("按账号可用模型及服务地域填写。")}</small>
            </label>
          </div>
          <label>API Key<input type="password" autoComplete="new-password" value={apiKey} maxLength={4000}
            onChange={(e) => setApiKey(e.target.value)} placeholder={t(configured ? "已配置此地址的密钥；留空继续使用" : "输入服务商提供的 API Key")} />
            <small>{t("密钥保存在本机，按接口地址分别保存；本机免鉴权服务可留空。")}</small>
          </label>
          <div className="settings-description model-requirements">
            <h3>{t("模型类型与能力要求")}</h3>
            <ul>
              <li>{t("选择文本生成 / 指令模型，支持多步骤推理、中英文分析与证据解读。")}</li>
              <li>{t("必须兼容 Chat Completions、system/user 消息和 JSON Object 输出。")}</li>
              <li>{t("建议上下文至少 32K，长报告优先 128K；支持原生工具调用的模型更便于扩展。")}</li>
            </ul>
            <p>{t("当前 Agent 用 JSON 指令调度分析工具。Embedding、重排、图像生成和专用决策模型不适合作为主 Agent。")}</p>
            <div className="model-source-links">{saved.presets.map((preset) => <a href={preset.source} key={preset.id} target="_blank" rel="noreferrer">{preset.name} {t("官方说明")} <ExternalLink size={12} /></a>)}</div>
          </div>
          <details className="model-advanced">
            <summary>{t("高级模型参数")}</summary>
            <div className="model-input-grid">
              <label>{t("最大输出 Token")}<input type="number" min={1024} max={131072} required value={config.max_tokens}
                onChange={(e) => setConfig({ ...config, max_tokens: Number(e.target.value) })} /></label>
              <label>{t("请求超时（秒）")}<input type="number" min={10} max={600} required value={config.timeout_seconds}
                onChange={(e) => setConfig({ ...config, timeout_seconds: Number(e.target.value) })} /></label>
            </div>
            <label>{t("附加生成参数（JSON）")}<textarea rows={4} spellCheck={false} value={extra} onChange={(e) => setExtra(e.target.value)} />
              <small>{t("可设置 enable_thinking、thinking、reasoning_effort、thinking_budget、temperature、top_p；按模型文档调整。")}</small>
            </label>
          </details>
          <p className="muted">{t("检测会发送一次简短模型请求，检查连接、指令遵循和 JSON 格式，并计入服务商用量。")}</p>
          <button className="primary" type="submit" disabled={busy || !config.model.trim() || !config.base_url.trim()}>
            <Save size={16} />{busy ? t("正在检测…") : t("检测并保存")}
          </button>
        </fieldset>
      </form>}
      {error && <p className="error" role="alert">{t(error)}</p>}
      {notice && <p className="success-text" role="status"><Check size={16} />{t(notice)}</p>}
    </Card>
  );
}
