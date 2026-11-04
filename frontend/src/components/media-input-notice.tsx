"use client";

import type { MediaInput } from "@/lib/types";
import { useI18n } from "./language-provider";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const messages: Record<string, string> = {
  model_text_only: "当前模型按纯文本模式运行。无论数据集是否包含图片，都只发送帖子文字，不读取或发送配图。",
  text_only_selected: "已选择仅分析文字，帖子配图将保留在数据集中，不参与本次分析。",
  image_limit_applied: "部分帖子超过配图上限，按原始顺序选取前 {limit} 张，其余配图保留在数据集中。",
  image_read_failed: "部分配图读取失败，对应帖子已标记为标注失败，请检查图片引用后重试。",
  empty_model_input: "部分帖子在当前模式下没有可分析的内容，已标记为标注失败。",
};

export function MediaInputNotice({ value, counts = false }: { value?: MediaInput | null; counts?: boolean }) {
  const { t } = useI18n();
  if (!value) return null;
  return (
    <div className="media-input-notice" role="status" aria-live="polite">
      {value.notices.map((notice) => (
        <p className={notice === "model_text_only" || notice === "image_read_failed" ? "warning-text" : "caption"} key={notice}>
          {t(messages[notice] ?? notice, { limit: value.max_images_per_post })}
        </p>
      ))}
      {counts && <p className="caption">{t("配图共 {total} 张；按每帖上限选择 {selected} 张，忽略 {ignored} 张。", { total: value.available_images, selected: value.selected_images, ignored: value.ignored_images })}</p>}
    </div>
  );
}

/** Also show fallback notices for advanced JSON and Leader-generated requests. */
export function AppliedMediaNotice({ requestText }: { requestText: string }) {
  const [value, setValue] = useState<MediaInput>();
  let query = "";
  try {
    const request = JSON.parse(requestText);
    const provider = request.labels?.provider ?? "openai_decisions";
    const defaults: Record<string, string> = { openai_decisions: "gpt-6-luna", jev: "jev-latest", aliyun_decision: "decision-model-preview" };
    if (defaults[provider]) query = new URLSearchParams({ provider, model: request.labels?.model ?? defaults[provider], media_mode: request.media_mode ?? "text_image", max_images_per_post: String(request.labels?.max_images_per_post ?? 3) }).toString();
  } catch { /* The JSON editor displays syntax errors on submission. */ }
  useEffect(() => {
    let current = true;
    setValue(undefined);
    if (query) void api<MediaInput>(`/label-capabilities?${query}`).then((v) => { if (current) setValue(v); }).catch(() => {});
    return () => { current = false; };
  }, [query]);
  return <MediaInputNotice value={value} />;
}
