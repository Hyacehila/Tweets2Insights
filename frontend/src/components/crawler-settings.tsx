"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "./language-provider";
import { Card } from "./tremor/Card";
import { Badge } from "./tremor/Badge";

type Platform = { id: string; name: string; login_type: string; headless: boolean; timeout_seconds: number; cookie_configured: boolean };
type Settings = { installed: boolean; platforms: Platform[] };

export function CrawlerSettings() {
  const { t } = useI18n();
  const [value, setValue] = useState<Settings>();
  const [platform, setPlatform] = useState("wb");
  const [login, setLogin] = useState("qrcode");
  const [cookie, setCookie] = useState("");
  const [headless, setHeadless] = useState(false);
  const [timeout, setTimeout] = useState(1200);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  useEffect(() => { api<Settings>("/crawler-settings").then(setValue).catch(e => setError(e.message)); }, []);
  useEffect(() => {
    const config = value?.platforms.find(item => item.id === platform);
    if (config) { setLogin(config.login_type); setHeadless(config.headless); setTimeout(config.timeout_seconds); }
    setCookie(""); setNotice("");
  }, [platform, value]);
  async function save(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const data = await api<Settings>("/crawler-settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ platform, login_type: login, cookie: cookie || null, headless, timeout_seconds: timeout }) });
      setValue(data); setCookie(""); setNotice("配置已保存");
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <Card className="surface provider-form"><div className="section-heading"><h2>MediaCrawler</h2><Badge variant={value?.installed ? "success" : "neutral"}>{t(value?.installed ? "已安装" : "未安装")}</Badge></div>
    <p className="muted">{t("按平台保存登录方式；采集时自动使用对应的会话。")}</p>
    {!value?.installed && <pre className="trace-output">uv run --project backend python scripts/setup_mediacrawler.py</pre>}
    <div className="filterbar">{value?.platforms.map(item => <button key={item.id} aria-pressed={platform === item.id} className={platform === item.id ? "selected" : ""} onClick={() => setPlatform(item.id)}>{t(item.name)}</button>)}</div>
    <form onSubmit={save}><label>{t("登录方式")}<select value={login} onChange={e => setLogin(e.target.value)}><option value="qrcode">{t("扫码登录")}</option><option value="cookie">Cookie</option></select></label>
      {login === "qrcode" ? <p className="caption">{t("首次采集时会打开浏览器，请完成扫码或平台验证。登录状态保存在本机。")}</p> : <label>Cookie<input type="password" autoComplete="new-password" value={cookie} onChange={e => setCookie(e.target.value)} placeholder={t(value?.platforms.find(item => item.id === platform)?.cookie_configured ? "已保存，留空保留现有 Cookie" : "输入平台 Cookie")} /></label>}
      <label>{t("采集超时（秒）")}<input type="number" min={60} max={7200} value={timeout} onChange={e => setTimeout(+e.target.value)} /></label>
      {login === "cookie" && <label className="check-label"><input type="checkbox" checked={headless} onChange={e => setHeadless(e.target.checked)} />{t("后台浏览器模式")}</label>}
      {error && <p role="alert" className="error">{error}</p>}{notice && <p role="status" className="success-text">{t(notice)}</p>}
      <button className="primary" disabled={busy || !value}>{t(busy ? "正在保存…" : "保存配置")}</button>
    </form>
  </Card>;
}
