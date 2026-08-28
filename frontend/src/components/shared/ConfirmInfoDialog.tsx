"use client";

import type { ReactNode } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * 确认信息核对弹窗共享壳（#248）：
 * 三态内容区（加载骨架 / 后端错误 / 字段内容）+ 二次确认按钮。
 * 预览加载中或失败时禁用确认按钮，失败错误直接展示在弹窗内（不静默吞错）。
 */
interface ConfirmInfoDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  /** 预览请求进行中 */
  isLoading?: boolean;
  /** 预览请求失败的后端错误信息 */
  error?: string | null;
  onConfirm: () => void;
  /** 确认请求进行中 */
  isConfirming?: boolean;
  confirmLabel?: string;
  children: ReactNode;
}

export function ConfirmInfoDialog({
  open,
  onOpenChange,
  title,
  description,
  isLoading = false,
  error = null,
  onConfirm,
  isConfirming = false,
  confirmLabel = "确认",
  children,
}: ConfirmInfoDialogProps) {
  const blocked = isLoading || !!error || isConfirming;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description ? <DialogDescription>{description}</DialogDescription> : null}
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            正在计算预览…
          </div>
        ) : error ? (
          <div className="rounded-md bg-destructive-soft px-3 py-2 text-sm text-destructive-foreground">
            预览失败：{error}
          </div>
        ) : (
          <div className="divide-y divide-border">{children}</div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isConfirming}>
            取消
          </Button>
          <Button onClick={onConfirm} disabled={blocked}>
            {isConfirming && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** 字段行：左侧灰色标签 + 右侧数值（金融数字由调用方经 lib/utils 格式化） */
export function InfoRow({
  label,
  value,
  valueClassName,
}: {
  label: string;
  value: ReactNode;
  valueClassName?: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5 text-sm">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <span className={cn("text-right font-medium tabular-nums", valueClassName)}>{value}</span>
    </div>
  );
}
