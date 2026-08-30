"use client";

import { ConfirmInfoDialog, InfoRow } from "@/components/shared/ConfirmInfoDialog";
import { useProduct } from "@/hooks/useProduct";
import type { ShareChangeEvent } from "@/types/share-change-event";
import type { EventType } from "@/types/common";
import { formatCurrency, formatShares, formatDate } from "@/lib/utils";

export const EVENT_TYPE_LABELS: Record<EventType, string> = {
  cash_dividend: "现金分红",
  reinvest_dividend: "分红再投资",
  share_split: "份额拆分",
  share_merge: "份额合并",
  bonus_share: "红股送股",
  forced_adjustment: "强制调整",
};

/**
 * 份额变动事件确认信息核对弹窗（#248）：
 * 事件字段均已落库，无需预览请求；确认按钮二次点击才发起确认。
 */
interface EventConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  event: ShareChangeEvent | null;
  platformNameMap: Map<string, string>;
  onConfirm: () => void;
  isConfirming?: boolean;
}

export function EventConfirmDialog({
  open,
  onOpenChange,
  event,
  platformNameMap,
  onConfirm,
  isConfirming = false,
}: EventConfirmDialogProps) {
  // 产品名按单条事件懒加载（enabled 由 code 门控）：整页 productNameMap 方案受
  // page_size=100 截断，产品超限时弹窗只剩裸代码（#257 评审）；market 用于 LOF 消歧，
  // 查询失败/无产品时回退展示裸代码
  const { data: product } = useProduct(event?.product_code ?? "", event?.market || undefined);
  // product_code 类型上可选：缺失时展示 "--"（InfoRow 不做空值兜底）
  const getProductName = () => {
    if (!event?.product_code) return "--";
    return product ? `${product.name}（${event.product_code}）` : event.product_code;
  };

  return (
    <ConfirmInfoDialog
      open={open}
      onOpenChange={onOpenChange}
      title="确认份额变动事件"
      description="请核对以下信息，确认后将生效"
      isLoading={false}
      onConfirm={onConfirm}
      isConfirming={isConfirming}
    >
      {event && (
        <>
          <InfoRow label="事件类型" value={EVENT_TYPE_LABELS[event.event_type] || event.event_type} />
          <InfoRow label="产品" value={getProductName()} />
          <InfoRow
            label="平台"
            value={
              event.platform_code
                ? platformNameMap.get(event.platform_code) ?? event.platform_code
                : "--"
            }
          />
          <InfoRow label="份额变化" value={formatShares(event.shares_change)} />
          <InfoRow label="现金变化" value={formatCurrency(event.cash_change)} />
          <InfoRow label="权益登记日" value={formatDate(event.entitlement_date)} />
          <InfoRow label="除息日" value={formatDate(event.ex_date)} />
        </>
      )}
    </ConfirmInfoDialog>
  );
}
