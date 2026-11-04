"use client";
import { useI18n } from "./language-provider";
import * as Dialog from "@radix-ui/react-dialog";
import { X, Inbox } from "lucide-react";
import { Badge } from "./tremor/Badge";

export const statusLabels: Record<string, string> = {
  queued: "等待执行",
  running: "执行中",
  waiting_for_auth: "等待授权",
  cancelled: "已取消",
  cancel_requested: "正在取消",
  partial: "部分完成",
  completed: "已完成",
  failed: "执行失败",
  interrupted: "已中断",
};
export function StatusBadge({ status }: { status?: string }) {
  const { t } = useI18n();
  const variant =
    status === "completed"
      ? "success"
      : status === "failed"
        ? "error"
        : ["partial", "waiting_for_auth", "interrupted"].includes(status ?? "")
          ? "warning"
          : status === "running"
            ? "default"
            : "neutral";
  return (
    <Badge variant={variant}>
      <span className="badge-dot" />
      {t(statusLabels[status ?? ""] ?? status ?? "未开始")}
    </Badge>
  );
}
export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Inbox size={23} />
      </span>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}
export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
}: {
  open: boolean;
  onOpenChange: (value: boolean) => void;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  const { t } = useI18n();
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="modal-overlay" />
        <Dialog.Content className="modal-content">
          <Dialog.Title className="modal-title">{title}</Dialog.Title>
          <Dialog.Description className="muted">
            {description}
          </Dialog.Description>
          <Dialog.Close
            className="icon-button modal-close"
            aria-label={t("关闭")}
          >
            <X size={18} />
          </Dialog.Close>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function formatDate(value: string, locale = "zh-CN") {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString(locale, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
}
