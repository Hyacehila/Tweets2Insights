"use client";
import { useI18n } from "./language-provider";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { MediaInput } from "@/lib/types";
import { MediaInputNotice } from "./media-input-notice";
import { workflowState } from "@/lib/workflow-state";

const phaseLabels: Record<string, string> = {
  retrospective: "事件复盘",
  forecast: "训练与预测",
  scenario: "调控模拟与建议",
};
const roleLabels: Record<string, string> = {
  data: "数据分析",
  search: "搜索补证",
  visual: "图表解读",
  insight: "综合解释",
  methodology: "方法检查",
};

export function WorkflowBuilder({
  eventId,
  dataset,
  keywords,
  onKeywordsChange,
  searchProvider,
  savedRequest,
  onBuild,
  onDirty,
}: {
  eventId: string;
  dataset: string;
  keywords: string;
  onKeywordsChange: (value: string) => void;
  searchProvider: string;
  savedRequest?: unknown;
  onBuild: (text: string) => void;
  onDirty: () => void;
}) {
  const { t } = useI18n();
  const [input, setInput] = useState("existing");
  const [phases, setPhases] = useState(["retrospective"]);
  const [roles, setRoles] = useState(Object.keys(roleLabels));
  const [start, setStart] = useState(
    new Date(Date.now() - 14 * 86400000).toISOString().slice(0, 16),
  );
  const [end, setEnd] = useState(new Date().toISOString().slice(0, 16));
  const [labelProvider, setLabelProvider] = useState("openai_decisions");
  const [model, setModel] = useState("gpt-6-luna");
  const [mediaMode, setMediaMode] = useState("text_image");
  const [maxImages, setMaxImages] = useState(3);
  const [capability, setCapability] = useState<MediaInput>();
  const [capabilityError, setCapabilityError] = useState("");
  useEffect(() => {
    let current = true;
    setCapability(undefined);
    setCapabilityError("");
    const query = new URLSearchParams({ provider: labelProvider, model, media_mode: mediaMode, max_images_per_post: String(maxImages) });
    api<MediaInput>(`/label-capabilities?${query}`)
      .then((value) => { if (current) setCapability(value); })
      .catch(() => { if (current) setCapabilityError("暂时无法读取模型图片能力，请检查服务连接。"); });
    return () => { current = false; };
  }, [labelProvider, model, mediaMode, maxImages]);
  const [platforms, setPlatforms] = useState("wb");
  const [maxComments, setMaxComments] = useState(0);
  const [maxPages, setMaxPages] = useState(20);
  const [collectImages, setCollectImages] = useState(true);
  const [rounds, setRounds] = useState(3);
  const [horizon, setHorizon] = useState(7);
  const [maxPosts, setMaxPosts] = useState(500);
  const [maxCalls, setMaxCalls] = useState(600);
  const [instruction, setInstruction] = useState("");
  const [mechanism, setMechanism] = useState("state_shift");
  const [measure, setMeasure] = useState<string | undefined>(undefined);
  const [magnitude, setMagnitude] = useState(0.1);
  const [cost, setCost] = useState(0);
  const [assumption, setAssumption] = useState<string | undefined>(undefined);
  const [error, setError] = useState("");
  useEffect(() => {
    const state = workflowState(savedRequest);
    if (!state) return;
    if (state.input !== undefined) setInput(state.input === "upload" ? "existing" : state.input);
    if (state.phases !== undefined) setPhases(state.phases);
    if (state.roles !== undefined) setRoles(state.roles);
    if (state.start !== undefined) setStart(state.start);
    if (state.end !== undefined) setEnd(state.end);
    if (state.labelProvider !== undefined) setLabelProvider(state.labelProvider);
    if (state.model !== undefined) setModel(state.model);
    if (state.mediaMode !== undefined) setMediaMode(state.mediaMode);
    if (state.maxImages !== undefined) setMaxImages(state.maxImages);
    if (state.maxCalls !== undefined) setMaxCalls(state.maxCalls);
    if (state.rounds !== undefined) setRounds(state.rounds);
    if (state.horizon !== undefined) setHorizon(state.horizon);
    if (state.maxPosts !== undefined) setMaxPosts(state.maxPosts);
    if (state.maxComments !== undefined) setMaxComments(state.maxComments);
    if (state.maxPages !== undefined) setMaxPages(state.maxPages);
    if (state.collectImages !== undefined) setCollectImages(state.collectImages);
    if (state.platforms !== undefined) setPlatforms(state.platforms);
    if (state.instruction !== undefined) setInstruction(state.instruction);
    if (state.mechanism !== undefined) setMechanism(state.mechanism);
    if (state.measure !== undefined) setMeasure(state.measure);
    if (state.magnitude !== undefined) setMagnitude(state.magnitude);
    if (state.cost !== undefined) setCost(state.cost);
    if (state.assumption !== undefined) setAssumption(state.assumption);
  }, [savedRequest]);
  function build() {
    try {
      if (
        !phases.length ||
        (input === "keywords" && !keywords.trim()) ||
        (input === "existing" && !dataset)
      )
        throw new Error("请选择阶段和输入数据；关键词采集时须填写关键词。");
      const begin = new Date(start + "Z"),
        finish = new Date(end + "Z");
      if (!(begin < finish) || finish > new Date())
        throw new Error("时间范围须有效，结束时间不得晚于当前时间。");
      const numeric = phases.some((p) => p !== "retrospective");
      if (input === "keywords" && !platforms) throw new Error("请选择至少一个采集平台。");
      if (!Number.isInteger(maxImages) || maxImages < 1 || maxImages > 9)
        throw new Error("每帖配图上限必须是 1–9 的整数。");
      const request = {
        event: {
          event_id: eventId,
          input_mode: input,
          dataset_ref: input === "existing" ? dataset : null,
          keywords: (input === "keywords" ? keywords : "")
            .split(/[,，]/)
            .map((s) => s.trim())
            .filter(Boolean),
          start: begin.toISOString(),
          end: finish.toISOString(),
          as_of: finish.toISOString(),
          search_provider: searchProvider,
          objectives: phases,
        },
        run_id: `run-${Date.now()}`,
        crawl:
          input === "keywords"
            ? {
                platforms: platforms
                  .split(/[,，]/)
                  .map((s) => s.trim())
                  .filter(Boolean),
                max_posts: maxPosts,
                max_comments: maxComments,
                max_pages: maxPages,
                collect_images: collectImages,
                max_images_per_post: maxImages,
              }
            : null,
        labels: {
          provider: labelProvider,
          model,
          batch_size: 1,
          max_calls: maxCalls,
          confidence_threshold: 0.7,
          probability_margin: 0.1,
          max_images_per_post: maxImages,
        },
        media_mode: mediaMode,
        observations: {
          start: begin.toISOString(),
          end: finish.toISOString(),
          window_seconds: 86400,
        },
        sampling: {
          sample_size: 30,
          high_read_quantile: 0.75,
          seed: 42,
          missing_reads: "uniform",
        },
        analysis: { forum_roles: roles, instruction, max_tool_calls: 24 },
        forum_rounds: rounds,
        model: numeric
          ? {
              algorithm: "latent_hk_enkf",
              latent_dimensions: 6,
              calibrate: true,
              training_cutoff: finish.toISOString(),
              horizon,
            }
          : null,
        scenarios: phases.includes("scenario")
          ? [
              {
                scenario_id: "measure-1",
                measure: measure ?? t("信息澄清情景"),
                mechanism,
                dimension: "stance",
                start_step: 1,
                duration: Math.min(3, horizon),
                shift: mechanism === "state_shift" ? magnitude : 0,
                parameter_value: mechanism === "state_shift" ? null : magnitude,
                resource_cost: cost,
                assumptions: [
                  assumption ?? t("说明该措施影响公众意见的机制与适用条件。"),
                ],
              },
            ]
          : [],
        max_total_calls: maxCalls + 60,
      };
      onBuild(JSON.stringify(request, null, 2));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const toggle = (items: string[], key: string) =>
    items.includes(key) ? items.filter((v) => v !== key) : [...items, key];
  return (
    <div className="workflow-builder" onChangeCapture={onDirty}>
      <label>
        {t("输入方式")}
        <select aria-label={t("输入方式")} value={input} onChange={(e) => setInput(e.target.value)}>
          <option value="existing">{t("上传 / 已有数据")}</option>
          <option value="keywords">{t("关键词与时间范围采集")}</option>
        </select>
      </label>
      {input === "keywords" && (
        <>
          <label>{t("事件关键词")}<input value={keywords} onChange={e => onKeywordsChange(e.target.value)} placeholder={t("例如：城市暴雨、交通出行")} /></label>
          <fieldset className="phase-options"><legend>MediaCrawler · {t("采集平台")}</legend>{Object.entries({ wb: "微博", xhs: "小红书", dy: "抖音", ks: "快手", bili: "哔哩哔哩", tieba: "百度贴吧", zhihu: "知乎" }).map(([id, name]) => <label className="check-label" key={id}><input type="checkbox" checked={platforms.split(",").includes(id)} onChange={() => setPlatforms(toggle(platforms.split(",").filter(Boolean), id).join(","))} />{t(name)}</label>)}</fieldset>
          <label>
            {t("采集上限")}
            <input
              type="number"
              min={1}
              max={100000}
              value={maxPosts}
              onChange={(e) => setMaxPosts(+e.target.value)}
            />
          </label>
          <div className="field-grid"><label>{t("评论总上限")}<input type="number" min={0} max={100000} value={maxComments} onChange={e => setMaxComments(+e.target.value)} /></label><label>{t("每个平台最多搜索页数")}<input type="number" min={1} max={10000} value={maxPages} onChange={e => setMaxPages(+e.target.value)} /></label></div>
          <label className="check-label"><input type="checkbox" checked={collectImages} onChange={e => setCollectImages(e.target.checked)} />{t("同时采集帖子配图")}</label>
          <p className="caption">{t("平台登录与 Cookie 在 API 设置中的 MediaCrawler 配置。")}</p>
        </>
      )}
      {input === "existing" && <p className="caption">{t("事件关键词将由智能体从抽样帖子中提取。")}</p>}
      <fieldset className="phase-options">
        <legend>{t("执行阶段")}</legend>
        {Object.entries(phaseLabels).map(([key, label]) => (
          <label
            className={`check-label ${phases.includes(key) ? "checked" : ""}`}
            key={key}
          >
            <input
              type="checkbox"
              checked={phases.includes(key)}
              onChange={() => setPhases(toggle(phases, key))}
            />
            {t(label)}
          </label>
        ))}
      </fieldset>
      <label>
        {t("起始时间（UTC）")}
        <input
          type="datetime-local"
          value={start}
          onChange={(e) => setStart(e.target.value)}
        />
      </label>
      <label>
        {t("截止时间（UTC）")}
        <input
          type="datetime-local"
          value={end}
          onChange={(e) => setEnd(e.target.value)}
        />
      </label>
      <label>
        {t("标注模型")}
        <select
          value={labelProvider}
          onChange={(e) => {
            setLabelProvider(e.target.value);
            setModel(
              {
                openai_decisions: "gpt-6-luna",
                jev: "jev-latest",
                aliyun_decision: "decision-model-preview",
              }[e.target.value] ?? "",
            );
          }}
        >
          <option value="openai_decisions">{t("OpenAI Decisions（默认）")}</option>
          <option value="jev">TypeSafe Jev</option>
          <option value="aliyun_decision">{t("阿里 decision")}</option>
        </select>
      </label>
      <label>
        {t("模型 ID")}
        <input value={model} readOnly={labelProvider === "openai_decisions"} onChange={(e) => setModel(e.target.value)} />
        {labelProvider === "openai_decisions" && <small>{t("使用 gpt-6-luna 的 Decisions API，返回五个标注字段及类别概率。")}</small>}
      </label>
      <label>
        {t("帖子输入模态")}
        <select value={capability?.supports_images === false ? "text_only" : mediaMode}
          disabled={capability?.supports_images === false} onChange={(e) => setMediaMode(e.target.value)}>
          <option value="text_image">{t("图文联合（无配图时使用文字）")}</option>
          <option value="text_only">{t("仅分析文字")}</option>
        </select>
      </label>
      <label>
        {t("每帖配图上限")}
        <input type="number" min={1} max={9} step={1} value={maxImages}
          disabled={capability?.effective_mode === "text_only"}
          onChange={(e) => setMaxImages(Number(e.target.value))} />
        <small>{t("默认 3 张，可选 1–9 张；按配图顺序选取，超出部分保留在原数据中。")}</small>
      </label>
      <MediaInputNotice value={capability} />
      {capability?.supports_images && mediaMode !== "text_only" && <p className="caption">{t("系统按所选模型自动转换图片格式，与帖子文字一起提交标注。")}</p>}
      {labelProvider === "jev" && capability?.supports_images && <p className="caption">{t("Jev 图片输入为实验功能，系统自动启用并适配图片尺寸。")}</p>}
      {capabilityError && <p className="warning-text">{t(capabilityError)}</p>}
      <label>
        {t("标注调用上限")}
        <input
          type="number"
          min={1}
          max={9940}
          value={maxCalls}
          onChange={(e) => setMaxCalls(+e.target.value)}
        />
      </label>
      {phases.includes("retrospective") && (
        <details>
          <summary>{t("论坛角色与研究要求")}</summary>
          {Object.entries(roleLabels).map(([key, label]) => (
            <label className="check-label" key={key}>
              <input
                type="checkbox"
                checked={roles.includes(key)}
                onChange={() => setRoles(toggle(roles, key))}
              />
              {t(label)}
            </label>
          ))}
          <label>
            {t("最多讨论轮数")}
            <input
              type="number"
              min={0}
              max={8}
              value={rounds}
              onChange={(e) => setRounds(+e.target.value)}
            />
          </label>
          <label>
            {t("分析关注点")}
            <textarea
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder={t("希望比较的群体、阶段、话题或问题")}
            />
          </label>
        </details>
      )}
      {phases.some((p) => p !== "retrospective") && (
        <label>
          {t("预测窗口数 · PCA + HK 实验模型")}
          <input
            type="number"
            min={1}
            max={100}
            value={horizon}
            onChange={(e) => setHorizon(+e.target.value)}
          />
        </label>
      )}
      {phases.includes("scenario") && (
        <details open>
          <summary>{t("调控情景")}</summary>
          <label>
            {t("措施描述")}
            <input
              value={measure ?? t("信息澄清情景")}
              onChange={(e) => setMeasure(e.target.value)}
            />
          </label>
          <label>
            {t("模型作用机制")}
            <select
              value={mechanism}
              onChange={(e) => setMechanism(e.target.value)}
            >
              <option value="state_shift">{t("立场状态偏移")}</option>
              <option value="confidence_change">{t("改变置信邻域")}</option>
              <option value="relaxation_change">{t("改变互动松弛率")}</option>
            </select>
          </label>
          <label>
            {t("偏移 / 参数值")}
            <input
              type="number"
              step={0.05}
              value={magnitude}
              onChange={(e) => setMagnitude(+e.target.value)}
            />
          </label>
          <label>
            {t("资源成本（自行定义单位）")}
            <input
              type="number"
              min={0}
              value={cost}
              onChange={(e) => setCost(+e.target.value)}
            />
          </label>
          <label>
            {t("机制假设")}
            <textarea
              value={
                assumption ?? t("说明该措施影响公众意见的机制与适用条件。")
              }
              onChange={(e) => setAssumption(e.target.value)}
            />
          </label>
          <p className="caption">
            {t("可在高级运行配置中添加更多情景，比较立场分布变化与资源成本。")}
          </p>
        </details>
      )}
      <button className="primary" onClick={build}>
        {t("应用研究配置")}
      </button>
      {error && <p className="error">{t(error)}</p>}
    </div>
  );
}
