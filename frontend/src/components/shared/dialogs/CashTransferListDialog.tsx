"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import { formatCurrency, getStatusBadgeVariant } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { useCashTransferList, useConfirmCashTransfer } from "@/hooks/useCashTransfer";

interface CashTransferListDialogProps {
  portfolioCode: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * 现金转移记录列表（按 transfer_group 分组）。
 * 跨天转移创建后两腿均 pending，需在此手动"确认到账"完成资金落地
 * （issue：此前 confirm 端点无任何 UI 入口，跨天转移永久卡在 pending）。
 */
export default function CashTransferListDialog({
  portfolioCode,
  open,
  onOpenChange,
}: CashTransferListDialogProps) {
  const { data, isLoading } = useCashTransferList(portfolioCode, { page_size: 50 });
  const confirmTransfer = useConfirmCashTransfer(portfolioCode);

  const transfers = data?.items || [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[720px]">
        <DialogHeader>
          <DialogTitle>现金转移记录</DialogTitle>
          <DialogDescription>
            平台间现金转移历史；跨天转移需在到账后手动确认
          </DialogDescription>
        </DialogHeader>
        {isLoading ? (
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            加载中...
          </div>
        ) : transfers.length === 0 ? (
          <div className="text-center text-muted-foreground py-8">暂无转移记录</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>转移日期</TableHead>
                <TableHead>转出 → 转入</TableHead>
                <TableHead className="number-cell">金额</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>状态</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {transfers.map((t) => {
                // 对称状态：两腿同 pending = 在途；同 confirmed = 已完成
                const isPending = t.sell_status === "pending";
                return (
                  <TableRow key={t.transfer_group}>
                    <TableCell>{t.transfer_date}</TableCell>
                    <TableCell>
                      {t.from_platform} → {t.to_platform}
                    </TableCell>
                    <TableCell className="number-cell">{formatCurrency(t.amount)}</TableCell>
                    <TableCell>{t.cross_day ? "跨天到账" : "当天完成"}</TableCell>
                    <TableCell>
                      <Badge variant={isPending ? "warning" : getStatusBadgeVariant(t.sell_status)}>
                        {isPending ? "在途" : t.sell_status === "confirmed" ? "已完成" : "已取消"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      {isPending && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => confirmTransfer.mutate(t.transfer_group)}
                          disabled={confirmTransfer.isPending}
                        >
                          {confirmTransfer.isPending && (
                            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                          )}
                          确认到账
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </DialogContent>
    </Dialog>
  );
}
