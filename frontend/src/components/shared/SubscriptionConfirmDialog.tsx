"use client";

import { ConfirmInfoDialog, InfoRow } from "./ConfirmInfoDialog";
import { useSubscriptionPreview } from "@/hooks/useTrade";
import { getErrorMessage } from "@/lib/api";
import { formatCurrency, formatShares, formatNav, formatDate } from "@/lib/utils";

/**
 * 申购赎回确认信息核对弹窗（#248）：
 * 打开时拉取后端确认预览（与真实确认共用计算实现），
 * 展示完整记录字段 + 预览份额/净值/金额/确认日；预览失败时展示错误并禁用确认。
 */
interface SubscriptionConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  subscriptionId: number | null;
  /** 列表行的申赎类型：预览失败时无响应数据，标题仍须正确（申购/赎回） */
  subType?: string;
  onConfirm: () => void;
  isConfirming?: boolean;
  investorNameMap: Map<string, string>;
  platformNameMap: Map<string, string>;
}

export function SubscriptionConfirmDialog({
  open,
  onOpenChange,
  subscriptionId,
  subType,
  onConfirm,
  isConfirming = false,
  investorNameMap,
  platformNameMap,
}: SubscriptionConfirmDialogProps) {
  const { data, isLoading, error } = useSubscriptionPreview(subscriptionId, open);
  const record = data?.subscription;
  const preview = data?.preview;
  const isSubscribe = (subType ?? record?.sub_type) === "subscribe";

  return (
    <ConfirmInfoDialog
      open={open}
      onOpenChange={onOpenChange}
      title={isSubscribe ? "确认申购" : "确认赎回"}
      description="请核对以下信息与预览值，确认后将不可直接修改"
      isLoading={isLoading}
      error={error ? getErrorMessage(error, "预览请求失败") : null}
      onConfirm={onConfirm}
      isConfirming={isConfirming}
    >
      {record && preview && (
        <>
          <InfoRow label="操作类型" value={isSubscribe ? "申购" : "赎回"} />
          <InfoRow
            label="投资人"
            value={investorNameMap.get(record.investor_code) ?? record.investor_code}
          />
          <InfoRow
            label="平台"
            value={platformNameMap.get(record.platform_code) ?? record.platform_code}
          />
          <InfoRow
            label="金额"
            value={formatCurrency(isSubscribe ? record.amount : preview.amount)}
          />
          <InfoRow
            label="份额"
            value={formatShares(isSubscribe ? preview.shares : record.shares)}
          />
          <InfoRow label="净值" value={formatNav(preview.nav)} />
          <InfoRow label="申请日期" value={formatDate(record.apply_date)} />
          <InfoRow label="确认日期" value={formatDate(preview.confirm_date)} />
        </>
      )}
    </ConfirmInfoDialog>
  );
}
