"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import MobileLayout from "@/components/mobile/MobileLayout";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatCurrency, formatNumber, formatReturnRate, getReturnColorClass } from "@/lib/utils";
import { ArrowLeft, Loader2, RefreshCw } from "lucide-react";
import Link from "next/link";
import { positionApi, platformApi } from "@/lib/api";
import { useUIStore } from "@/stores/uiStore";
import { usePositionList } from "@/hooks/usePosition";
import PositionCard from "@/components/shared/PositionCard";
import { DatePicker } from "@/components/ui/date-picker";

export default function MobilePositionsPage() {
  const params = useParams();
  const code = params.code as string;
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  const { data: positionsData, isLoading } = usePositionList(code);
  const positions = ((positionsData as any)?.items) || [];

  // 非净值资产更新相关状态
  const [isCashUpdateOpen, setIsCashUpdateOpen] = useState(false);
  const [cashAmount, setCashAmount] = useState("");
  const [selectedPlatform, setSelectedPlatform] = useState("");
  const [selectedDate, setSelectedDate] = useState<Date | undefined>(undefined);

  // 获取平台列表
  const { data: platformsData } = useQuery({
    queryKey: ["platforms"],
    queryFn: () => platformApi.list({ page_size: 100 }),
  });
  const platforms = ((platformsData as any)?.items) || [];

  const totalMarketValue = positions.reduce((sum: number, p: any) => sum + (p.market_value || 0), 0);
  const totalCost = positions.reduce((sum: number, p: any) => sum + ((p.shares || 0) * (p.cost_price || 0)), 0);
  const totalProfitLoss = totalMarketValue - totalCost;

  // 更新非净值资产的 mutation
  const updateCashPosition = useMutation({
    mutationFn: async ({ amount, platformCode, updateDate }: {
      amount: string;
      platformCode: string;
      updateDate?: string;
    }) => {
      return positionApi.updateCashPosition(code, parseFloat(amount), platformCode, updateDate);
    },
    onSuccess: () => {
      addToast({
        type: "success",
        title: "更新成功",
        message: "非净值资产金额已更新",
      });
      setIsCashUpdateOpen(false);
      setCashAmount("");
      setSelectedPlatform("");
      setSelectedDate(undefined);
      queryClient.invalidateQueries({ queryKey: ["positions", code] });
    },
    onError: (error: any) => {
      // 尝试从不同位置提取错误信息
      const errorMsg = 
        error.response?.data?.detail?.message || 
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message || 
        "更新失败，请检查网络连接或联系管理员";
      
      addToast({
        type: "error",
        title: "更新失败",
        message: errorMsg,
      });
    },
  });

  const handleCashUpdateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!cashAmount || parseFloat(cashAmount) < 0) {
      addToast({
        type: "error",
        title: "输入错误",
        message: "请输入有效的金额",
      });
      return;
    }
    
    if (!selectedPlatform) {
      addToast({
        type: "error",
        title: "输入错误",
        message: "请选择平台",
      });
      return;
    }
    
    if (selectedDate) {
      const dateStr = selectedDate.toISOString().split("T")[0];
      updateCashPosition.mutate({
        amount: cashAmount,
        platformCode: selectedPlatform,
        updateDate: dateStr,
      });
    } else {
      updateCashPosition.mutate({
        amount: cashAmount,
        platformCode: selectedPlatform,
      });
    }
  };

  if (isLoading) {
    return (
      <MobileLayout>
        <div className="flex items-center justify-center h-[60vh]">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </MobileLayout>
    );
  }

  return (
    <MobileLayout>
      <div className="space-y-4 p-4">
        {/* Header */}
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Link href={`/m/portfolio/${code}`}>
              <Button variant="ghost" size="sm">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <div>
              <h1 className="text-xl font-bold">持仓管理</h1>
              <p className="text-xs text-muted-foreground">{code}</p>
            </div>
          </div>
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => setIsCashUpdateOpen(true)}
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-3 gap-2">
          <Card>
            <CardContent className="p-3 text-center">
              <div className="text-sm font-bold">{formatCurrency(totalMarketValue)}</div>
              <p className="text-xs text-muted-foreground mt-1">总市值</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-3 text-center">
              <div className="text-sm font-bold">{formatCurrency(totalCost)}</div>
              <p className="text-xs text-muted-foreground mt-1">总成本</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-3 text-center">
              <div className={`text-sm font-bold ${getReturnColorClass(totalProfitLoss)}`}>
                {formatCurrency(totalProfitLoss)}
              </div>
              <p className="text-xs text-muted-foreground mt-1">总收益</p>
            </CardContent>
          </Card>
        </div>

        {/* Positions List */}
        <div className="space-y-3">
          {positions.length === 0 ? (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                暂无持仓数据
              </CardContent>
            </Card>
          ) : (
            positions.map((position: any) => (
              <PositionCard
                key={position.id}
                productCode={position.product_code}
                productName={position.product_name}
                market={position.market}
                shares={position.shares}
                costPrice={position.cost_price}
                currentPrice={position.unit_price}
                marketValue={position.market_value}
                profitLoss={position.profit_loss}
                profitLossPercent={position.profit_loss_percent}
              />
            ))
          )}
        </div>

        {/* Action Buttons */}
        <div className="space-y-2">
          <Link href={`/m/portfolio/${code}/trades`}>
            <Button className="w-full">
              调仓交易
            </Button>
          </Link>
        </div>

        {/* 非净值资产更新对话框 */}
        <Dialog open={isCashUpdateOpen} onOpenChange={setIsCashUpdateOpen} modal={false}>
          <DialogContent className="max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>更新非净值资产</DialogTitle>
              <DialogDescription>
                更新现金等非净值型资产的当前金额
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleCashUpdateSubmit}>
              <div className="space-y-4 py-4">
                {/* 平台选择 */}
                <div className="space-y-2">
                  <Label htmlFor="platform">平台</Label>
                  <Select value={selectedPlatform} onValueChange={setSelectedPlatform} required>
                    <SelectTrigger>
                      <SelectValue placeholder="请选择平台" />
                    </SelectTrigger>
                    <SelectContent>
                      {platforms.map((platform: any) => (
                        <SelectItem key={platform.code} value={platform.code}>
                          {platform.name} ({platform.code})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* 日期选择 */}
                <div className="space-y-2">
                  <Label>更新日期（可选）</Label>
                  <DatePicker
                    date={selectedDate}
                    onSelect={setSelectedDate}
                    placeholder="选择日期"
                  />
                  <p className="text-xs text-muted-foreground">
                    提示：只能选择交易日，非交易日将无法更新
                  </p>
                </div>

                {/* 金额输入 */}
                <div className="space-y-2">
                  <Label htmlFor="cash_amount">当前金额（元）</Label>
                  <Input
                    id="cash_amount"
                    type="number"
                    step="0.01"
                    min="0"
                    value={cashAmount}
                    onChange={(e) => setCashAmount(e.target.value)}
                    placeholder="请输入当前现金金额"
                    required
                  />
                </div>
              </div>
              <DialogFooter className="flex-col sm:flex-row gap-2">
                <Button 
                  type="button" 
                  variant="outline" 
                  onClick={() => setIsCashUpdateOpen(false)}
                  className="w-full sm:w-auto"
                >
                  取消
                </Button>
                <Button 
                  type="submit" 
                  disabled={updateCashPosition.isPending}
                  className="w-full sm:w-auto"
                >
                  {updateCashPosition.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  确认更新
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
    </MobileLayout>
  );
}
