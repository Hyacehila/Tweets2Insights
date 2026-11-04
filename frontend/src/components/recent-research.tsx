"use client";

import { useState } from "react";
import Link from "next/link";
import * as ContextMenu from "@radix-ui/react-context-menu";
import { Pencil, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import type { Thread } from "@/lib/types";
import { useI18n } from "./language-provider";
import { Modal } from "./ui";

export function RecentResearch({ threads, threadId, onDeleted, onRenamed }: {
  threads: Thread[];
  threadId?: string;
  onDeleted: (eventId: string, threadIds: string[]) => void;
  onRenamed: (thread: Thread) => void;
}) {
  const { t } = useI18n();
  const [selected, setSelected] = useState<Thread>();
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");
  const [renaming, setRenaming] = useState<Thread>();
  const [newTitle, setNewTitle] = useState("");
  const [saving, setSaving] = useState(false);

  async function rename(e: React.FormEvent) {
    e.preventDefault();
    if (!renaming || !newTitle.trim() || saving) return;
    setSaving(true); setError("");
    try {
      const result = await api<Thread>(`/threads/${renaming.thread_id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: newTitle.trim() }) });
      onRenamed(result); setRenaming(undefined);
    } catch (e) { setError((e as Error).message); }
    finally { setSaving(false); }
  }

  async function deleteEvent() {
    if (!selected || deleting) return;
    setDeleting(true);
    setError("");
    try {
      const result = await api<{ event_id: string; deleted_thread_ids: string[] }>(
        `/threads/${selected.thread_id}/event`, { method: "DELETE" },
      );
      setSelected(undefined);
      onDeleted(result.event_id, result.deleted_thread_ids);
    } catch (e) {
      const message = (e as Error).message;
      setError(message === "event_has_active_work"
        ? "该事件仍有任务运行，请先停止 Agent 和分析任务，待任务结束后再删除。"
        : message === "not_found" ? "该研究已被删除，请刷新列表。" : message);
    } finally {
      setDeleting(false);
    }
  }

  return <>
    <nav className="recent-navigation" aria-label={t("研究会话")}>
      {threads.slice(0, 8).map((item) => (
        <ContextMenu.Root key={item.thread_id}>
          <ContextMenu.Trigger asChild>
            <Link href={`/workspace/chats/${item.thread_id}`}
              title={t("右键管理事件")}
              className={threadId === item.thread_id ? "selected" : ""}>
              <span className="session-dot" /><span>{item.title}</span>
            </Link>
          </ContextMenu.Trigger>
          <ContextMenu.Portal>
            <ContextMenu.Content className="research-context-menu" collisionPadding={12}>
              <ContextMenu.Label className="research-context-label">{item.title}</ContextMenu.Label>
              <ContextMenu.Item className="research-context-item" onSelect={() => {
                setError(""); setRenaming(item); setNewTitle(item.title);
              }}><Pencil size={15} />{t("重命名")}</ContextMenu.Item>
              <ContextMenu.Item className="research-context-delete" onSelect={() => {
                setError(""); setSelected(item);
              }}>
                <Trash2 size={15} />{t("删除事件")}
              </ContextMenu.Item>
            </ContextMenu.Content>
          </ContextMenu.Portal>
        </ContextMenu.Root>
      ))}
      {!threads.length && <p className="sidebar-empty">{t("你的事件研究会出现在这里")}</p>}
    </nav>
    <Modal open={!!renaming} onOpenChange={open => { if (!open && !saving) setRenaming(undefined); }} title={t("重命名研究")} description="">
      <form onSubmit={rename}><label>{t("研究名称")}<input autoFocus required maxLength={120} value={newTitle} onFocus={e => e.target.select()} onChange={e => setNewTitle(e.target.value)} /></label>
        {error && <p className="error" role="alert">{error}</p>}
        <div className="modal-actions"><button type="button" disabled={saving} onClick={() => setRenaming(undefined)}>{t("取消")}</button><button className="primary" disabled={saving || !newTitle.trim()}>{t(saving ? "正在保存…" : "保存")}</button></div>
      </form>
    </Modal>
    <Modal open={!!selected} onOpenChange={(open) => {
      if (!open && !deleting) setSelected(undefined);
    }} title={t("删除事件")}
      description={t("将删除事件“{event}”下的全部研究会话、标注与分析结果、预测、情景模拟和报告。", { event: selected?.event_id ?? "" })}>
      <p className="delete-dataset-note">{t("数据集将保留。以后使用相同事件标识新建研究，即可继续使用这些数据。")}</p>
      {error && <p className="error" role="alert">{t(error)}</p>}
      <div className="modal-actions">
        <button type="button" disabled={deleting} onClick={() => setSelected(undefined)} autoFocus>{t("取消")}</button>
        <button type="button" className="danger-button" disabled={deleting} onClick={deleteEvent}>
          <Trash2 size={15} />{deleting ? t("正在删除…") : t("确认删除")}
        </button>
      </div>
    </Modal>
  </>;
}
