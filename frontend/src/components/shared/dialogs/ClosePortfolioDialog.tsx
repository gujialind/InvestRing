"use client";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import { Position } from "@/types/position";

interface PortfolioInvestorSummary {
  investor_code: string;
  name: string;
  shares: number;
}

interface ClosePortfolioDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  isPending?: boolean;
  positions: Position[];
  investors?: PortfolioInvestorSummary[];
}

/**
 * 关闭组合确认弹窗（桌面/移动端共用）。
 * 展示关闭前的校验提示：持仓、投资人份额、不可逆操作。
 */
export default function ClosePortfolioDialog({
  open,
  onOpenChange,
  onConfirm,
  isPending,
  positions,
  investors,
}: ClosePortfolioDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>关闭组合</AlertDialogTitle>
          <AlertDialogDescription>
            关闭组合前请确认以下事项：
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-2 text-sm">
          {positions.length > 0 && (
            <p className="text-yellow-600">
              当前仍有 {positions.length} 个持仓，关闭后持仓数据将被保留但不可操作
            </p>
          )}
          {investors && investors.length > 0 && (
            <p className="text-yellow-600">
              当前有 {investors.length} 位投资人持有份额
            </p>
          )}
          <p className="text-red-500">
            关闭后无法再进行申购/赎回/调仓操作
          </p>
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel>取消</AlertDialogCancel>
          <AlertDialogAction
            onClick={(e) => {
              e.preventDefault();
              onConfirm();
            }}
            disabled={isPending}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            确认关闭
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
