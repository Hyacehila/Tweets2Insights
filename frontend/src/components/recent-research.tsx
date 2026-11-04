"use client";

import { useState } from "react";
import Link from "next/link";
import * as ContextMenu from "@radix-ui/react-context-menu";
import { Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import type { Thread } from "@/lib/types";
import { useI18n } from "./language-provider";
import { Modal } from "./ui";

export function RecentResearch({ threads, threadId, onDeleted }: {
  threads: Thread[];
  threadId?: string;
  onDeleted: (eventId: string, threadIds: string[]) => void;
}) {
  const { t } = useI18n();
  const [selected, setSelected] = useState<Thread>();
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");

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
