"use client";
import { useI18n } from "./language-provider";
import { useState } from "react";

const phaseLabels: Record<string, string> = {
  retrospective: "事件复盘",
  forecast: "训练与预测",
  scenario: "调控模拟与建议",
  backtest: "历史回测",
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
  searchProvider,
  onBuild,
  onDirty,
}: {
  eventId: string;
  dataset: string;
  keywords: string;
  searchProvider: string;
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
  const [platforms, setPlatforms] = useState("x");
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
  function build() {
    try {
      if (
        !phases.length ||
        !keywords.trim() ||
        (input === "existing" && !dataset)
      )
        throw new Error("请选择阶段，并填写关键词及输入数据。");
      const begin = new Date(start + "Z"),
        finish = new Date(end + "Z");
      if (!(begin < finish) || finish > new Date())
        throw new Error("时间范围须有效，结束时间不得晚于当前时间。");
      const numeric = phases.some((p) => p !== "retrospective");
      const request = {
        event: {
          event_id: eventId,
          input_mode: input,
          dataset_ref: input === "existing" ? dataset : null,
          keywords: keywords
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
                max_comments: 0,
              }
            : null,
        labels: {
          provider: labelProvider,
          model,
          batch_size: labelProvider === "glm" ? 10 : 1,
          max_calls: maxCalls,
          confidence_threshold: 0.7,
          probability_margin: 0.1,
        },
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
                openai_decisions: "gpt-6-luna",
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
        <select value={input} onChange={(e) => setInput(e.target.value)}>
          <option value="existing">{t("上传 / 已有数据")}</option>
          <option value="keywords">{t("关键词与时间范围采集")}</option>
        </select>
      </label>
      {input === "keywords" && (
        <>
          <label>
            {t("平台 ID")}
            <input
              value={platforms}
              onChange={(e) => setPlatforms(e.target.value)}
            />
          </label>
          <p className="caption">
            {t("内置 X 官方归档搜索；其他平台使用本机安装的采集连接器。")}
          </p>
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
        </>
      )}
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
                jev: "jev-latest",
                aliyun_decision: "decision-model-preview",
                glm: "glm-4.5-air",
              }[e.target.value] ?? "",
            );
          }}
        >
          <option value="openai_decisions">{t("OpenAI Decisions（默认）")}</option>
          <option value="jev">TypeSafe Jev</option>
          <option value="aliyun_decision">{t("阿里 decision")}</option>
          <option value="glm">GLM JSON</option>
        </select>
      </label>
      <label>
        {t("模型 ID")}
        <input value={model} readOnly={labelProvider === "openai_decisions"} onChange={(e) => setModel(e.target.value)} />
        {labelProvider === "openai_decisions" && <small>{t("使用 gpt-6-luna 的 Decisions API，返回五个标注字段及类别概率。")}</small>}
      </label>
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
