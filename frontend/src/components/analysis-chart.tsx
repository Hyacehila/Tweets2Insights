"use client";
import { useI18n } from "./language-provider";
import { useState } from "react";
import {
  Area,
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AnalysisChart as SpecialtyChart,
  type ChartData,
  type ChartRow,
} from "./specialty-chart";
export type { ChartData, ChartRow } from "./specialty-chart";

const colors = [
  "#3b82f6",
  "#14b8a6",
  "#8b5cf6",
  "#f59e0b",
  "#f43f5e",
  "#64748b",
];

export function AnalysisChart({
  name,
  value,
}: {
  name: string;
  value: ChartData;
}) {
  const { t, locale } = useI18n();
  const numberFormat = (value: unknown) =>
    typeof value === "number"
      ? value.toLocaleString(locale, { maximumFractionDigits: 3 })
      : String(value ?? "—");
  const [chosen, setChosen] = useState("all");
  const [page, setPage] = useState(0);
  const source = value.data ?? value.table ?? [];
  const kind = value.chart?.kind ?? "bar";
  if (
    ["heatmap", "network", "wordcloud"].includes(kind) ||
    source.some((row) => "mass" in row)
  )
    return <SpecialtyChart name={name} value={value} />;
  const series = [
    ...new Set(source.map((row) => String(row.series ?? "数值"))),
  ];
  const selected = series.filter((item) => chosen === "all" || item === chosen);
  const rows = source
    .filter(
      (row) => chosen === "all" || String(row.series ?? "数值") === chosen,
    )
    .slice(0, 200);
  const groups = new Map<string, Record<string, unknown>>();
  for (const row of rows) {
    const label = String(row.label ?? "");
    const item = groups.get(label) ?? { label };
    const key = `s${series.indexOf(String(row.series ?? "数值"))}`;
    item[key] =
      typeof row.value === "number" && Number.isFinite(row.value)
        ? row.value
        : null;
    if (
      typeof row.lower === "number" &&
      typeof row.upper === "number" &&
      item[key] !== null
    )
      item[`${key}_range`] = [row.lower, row.upper];
    groups.set(label, item);
  }
  const chartRows = [...groups.values()];
  const hasValues = rows.some(
    (row) => typeof row.value === "number" && Number.isFinite(row.value),
  );
  const columns = [
    ...new Set(
      source
        .slice(0, 60)
        .flatMap((row) => Object.keys(row).filter((key) => key !== "post_ids")),
    ),
  ];
  return (
    <article className="analysis-chart">
      <div className="section-heading">
        <h3>{value.title ?? value.description ?? name}</h3>
        {series.length > 1 && (
          <select
            aria-label={t("选择图表序列")}
            value={chosen}
            onChange={(e) => {
              setChosen(e.target.value);
              setPage(0);
            }}
          >
            <option value="all">{t("所有序列")}</option>
            {series.map((item) => (
              <option key={item} value={item}>
                {t(item)}
              </option>
            ))}
          </select>
        )}
      </div>
      {hasValues ? (
        <>
          <div
            className="chart-container"
            role="img"
            aria-label={value.title ?? value.description ?? name}
          >
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              {kind === "pie" ? (
                <PieChart>
                  <Pie
                    data={rows.filter(
                      (row) => typeof row.value === "number" && row.value >= 0,
                    )}
                    dataKey="value"
                    nameKey="label"
                    innerRadius="58%"
                    outerRadius="83%"
                    paddingAngle={2}
                    stroke="none"
                    isAnimationActive={false}
                  >
                    {rows.map((_, i) => (
                      <Cell key={i} fill={colors[i % colors.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value) => numberFormat(value)}
                    contentStyle={{
                      background: "var(--surface)",
                      border: "1px solid var(--border)",
                      borderRadius: 7,
                      fontSize: 12,
                      color: "var(--text)",
                    }}
                  />
                </PieChart>
              ) : (
                <ComposedChart
                  data={chartRows}
                  margin={{ top: 10, right: 14, bottom: 8, left: 0 }}
                >
                  <CartesianGrid
                    stroke="var(--border)"
                    vertical={false}
                    strokeDasharray="3 3"
                  />
                  <XAxis
                    dataKey="label"
                    tickLine={false}
                    axisLine={false}
                    minTickGap={35}
                    tick={{ fill: "var(--muted)", fontSize: 10 }}
                    tickFormatter={(label) => String(label).slice(0, 16)}
                    dy={8}
                  />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    width={55}
                    tick={{ fill: "var(--muted)", fontSize: 10 }}
                    tickFormatter={numberFormat}
                  />
                  <Tooltip
                    formatter={(value) =>
                      Array.isArray(value)
                        ? value.map(numberFormat).join(" – ")
                        : numberFormat(value)
                    }
                    contentStyle={{
                      background: "var(--surface)",
                      border: "1px solid var(--border)",
                      borderRadius: 7,
                      fontSize: 12,
                      color: "var(--text)",
                    }}
                    cursor={{ fill: "var(--subtle)", stroke: "var(--border)" }}
                  />
                  {selected.map((item) => {
                    const index = series.indexOf(item),
                      key = `s${index}`,
                      color = colors[index % colors.length];
                    return kind === "line" ? (
                      <Area
                        key={`${key}-range`}
                        dataKey={`${key}_range`}
                        name={t("{series}区间", { series: t(item) })}
                        type="linear"
                        fill={color}
                        fillOpacity={0.12}
                        stroke="none"
                        connectNulls={false}
                        isAnimationActive={false}
                      />
                    ) : null;
                  })}
                  {selected.map((item) => {
                    const index = series.indexOf(item),
                      key = `s${index}`,
                      color = colors[index % colors.length];
                    return kind === "line" ? (
                      <Line
                        key={key}
                        dataKey={key}
                        name={t(item)}
                        stroke={color}
                        strokeWidth={2}
                        type="linear"
                        dot={false}
                        activeDot={{ r: 4 }}
                        connectNulls={false}
                        isAnimationActive={false}
                      />
                    ) : (
                      <Bar
                        key={key}
                        dataKey={key}
                        name={t(item)}
                        fill={color}
                        maxBarSize={36}
                        radius={[3, 3, 0, 0]}
                        isAnimationActive={false}
                      />
                    );
                  })}
                </ComposedChart>
              )}
            </ResponsiveContainer>
          </div>
          <div className="chart-legend">
            {(kind === "pie"
              ? rows.map((row) => String(row.label))
              : selected
            ).map((item, i) => (
              <span key={`${item}-${i}`}>
                <i
                  style={{
                    background:
                      colors[
                        (kind === "pie" ? i : series.indexOf(item)) %
                          colors.length
                      ],
                  }}
                />
                {t(item)}
              </span>
            ))}
          </div>
        </>
      ) : (
        <p className="caption">{t("当前数据没有可绘制的数值。")}</p>
      )}
      {value.notes?.map((note, i) => (
        <p className="caption" key={i}>
          {note}
        </p>
      ))}
      <details>
        <summary>
          {t("查看源数据 · {count} 行", {
            count: value.data_total ?? value.table_total ?? source.length,
          })}
        </summary>
        {value.coverage !== undefined && (
          <pre>{JSON.stringify(value.coverage, null, 2)}</pre>
        )}
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {source.slice(page * 10, (page + 1) * 10).map((row, i) => (
                <tr key={i}>
                  {columns.map((column) => (
                    <td key={column}>
                      {typeof row[column] === "object"
                        ? JSON.stringify(row[column])
                        : String(row[column] ?? t("缺失"))}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="actions">
          <button disabled={!page} onClick={() => setPage(page - 1)}>
            {t("上一页")}
          </button>
          <span className="caption">
            {t("第 {page} 页", { page: page + 1 })}
          </span>
          <button
            disabled={(page + 1) * 10 >= source.length}
            onClick={() => setPage(page + 1)}
          >
            {t("下一页")}
          </button>
        </div>
        <p className="caption">
          {t("图表显示当前预览数据，完整记录可通过产物下载。")}
        </p>
      </details>
    </article>
  );
}
