"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import MainLayout from "@/components/layout/MainLayout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
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
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Calendar } from "@/components/ui/calendar";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatCurrency, formatNumber, formatReturnRate, cn } from "@/lib/utils";
import { Plus, ArrowLeft, Loader2, RefreshCw, CalendarIcon } from "lucide-react";
import Link from "next/link";
import { tradeApi, positionApi, platformApi } from "@/lib/api";
import { useUIStore } from "@/stores/uiStore";
import { usePositionList } from "@/hooks/usePosition";
import { format } from "date-fns";
import { zhCN } from "date-fns/locale";

interface Position {
  id: number;
  product_code: string;
  product_name: string;
  market?: string;
  shares?: number;
  amount?: number;
  cost_price?: number;
  unit_price?: number;
  market_value?: number;
  profit_loss?: number;
  profit_loss_percent?: number;
}

export default function PositionsPage() {
  const params = useParams();
  const code = params.code as string;
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  const { data: positionsData, isLoading } = usePositionList(code);
  const positions = ((positionsData as any)?.items) as Position[] || [];

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [tradeType, setTradeType] = useState<"buy" | "sell">("buy");
  const [formData, setFormData] = useState({
    product_code: "",
    shares: "",
    amount: "",
    price: "",
  });

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

  const totalMarketValue = positions.reduce((sum, p) => sum + (p.market_value || 0), 0);
  const totalCost = positions.reduce((sum, p) => sum + ((p.shares || 0) * (p.cost_price || 0)), 0);
  const totalProfitLoss = totalMarketValue - totalCost;

  const createTrade = useMutation({
    mutationFn: tradeApi.create,
    onSuccess: () => {
      addToast({
        type: "success",
        title: "交易提交成功",
        message: "调仓交易已提交，等待确认",
      });
      setIsDialogOpen(false);
      setFormData({ product_code: "", shares: "", amount: "", price: "" });
      queryClient.invalidateQueries({ queryKey: ["trades", code] });
    },
    onError: (error: any) => {
      addToast({
        type: "error",
        title: "交易提交失败",
        message: error.message || "请检查输入数据后重试",
      });
    },
  });

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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.product_code || !formData.price) {
      addToast({
        type: "error",
        title: "表单校验失败",
        message: "请填写完整交易信息",
      });
      return;
    }

    const amount = tradeType === "buy" ? parseFloat(formData.amount || "0") : 0;
    const shares = tradeType === "sell" ? parseFloat(formData.shares || "0") : 0;

    if (tradeType === "buy" && (!amount || amount <= 0)) {
      addToast({
        type: "error",
        title: "表单校验失败",
        message: "买入金额必须大于0",
      });
      return;
    }

    if (tradeType === "sell" && (!shares || shares <= 0)) {
      addToast({
        type: "error",
        title: "表单校验失败",
        message: "卖出份额必须大于0",
      });
      return;
    }

    const tradeData = {
      portfolio_code: code,
      product_code: formData.product_code,
      trade_type: tradeType,
      trade_date: new Date().toISOString().split("T")[0],
      price: parseFloat(formData.price),
      ...(tradeType === "buy"
        ? { amount }
        : { shares }),
      fee: 0,
    };

    createTrade.mutate(tradeData as any);
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href={`/portfolio/${code}`}>
              <Button variant="ghost" size="sm">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <div>
              <h1 className="text-3xl font-bold tracking-tight">持仓管理</h1>
              <p className="text-muted-foreground">组合代码: {code}</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setIsCashUpdateOpen(true)}>
              <RefreshCw className="mr-2 h-4 w-4" />
              更新非净值资产
            </Button>
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="mr-2 h-4 w-4" />
                  调仓
                </Button>
              </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>调仓交易</DialogTitle>
                <DialogDescription>
                  提交买入或卖出交易
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={handleSubmit}>
                <div className="space-y-4 py-4">
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant={tradeType === "buy" ? "default" : "outline"}
                      onClick={() => setTradeType("buy")}
                      className="flex-1"
                    >
                      买入
                    </Button>
                    <Button
                      type="button"
                      variant={tradeType === "sell" ? "default" : "outline"}
                      onClick={() => setTradeType("sell")}
                      className="flex-1"
                    >
                      卖出
                    </Button>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="product_code">产品代码</Label>
                    <Input
                      id="product_code"
                      value={formData.product_code}
                      onChange={(e) => setFormData({ ...formData, product_code: e.target.value })}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="price">价格</Label>
                    <Input
                      id="price"
                      type="number"
                      step="0.0001"
                      value={formData.price}
                      onChange={(e) => setFormData({ ...formData, price: e.target.value })}
                      required
                    />
                  </div>
                  {tradeType === "buy" ? (
                    <div className="space-y-2">
                      <Label htmlFor="amount">买入金额</Label>
                      <Input
                        id="amount"
                        type="number"
                        value={formData.amount}
                        onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                        required
                      />
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <Label htmlFor="shares">卖出份额</Label>
                      <Input
                        id="shares"
                        type="number"
                        value={formData.shares}
                        onChange={(e) => setFormData({ ...formData, shares: e.target.value })}
                        required
                      />
                    </div>
                  )}
                </div>
                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setIsDialogOpen(false)}>
                    取消
                  </Button>
                  <Button type="submit" disabled={createTrade.isPending}>
                    {createTrade.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    提交
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>

          {/* 非净值资产更新对话框 */}
          <Dialog open={isCashUpdateOpen} onOpenChange={setIsCashUpdateOpen} modal={false}>
            <DialogContent className="sm:max-w-[500px]">
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
                    <Label>更新日期（可选，默认为今天）</Label>
                    <Popover>
                      <PopoverTrigger asChild>
                        <Button
                          variant="outline"
                          className={cn(
                            "w-full justify-start text-left font-normal",
                            !selectedDate && "text-muted-foreground"
                          )}
                        >
                          <CalendarIcon className="mr-2 h-4 w-4" />
                          {selectedDate ? format(selectedDate, "yyyy-MM-dd") : "选择日期"}
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-auto p-0" side="bottom" align="start">
                        <Calendar
                          mode="single"
                          selected={selectedDate}
                          onSelect={setSelectedDate}
                          locale={zhCN}
                          disabled={(date) => date > new Date()}
                        />
                      </PopoverContent>
                    </Popover>
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
                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setIsCashUpdateOpen(false)}>
                    取消
                  </Button>
                  <Button type="submit" disabled={updateCashPosition.isPending}>
                    {updateCashPosition.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    确认更新
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>持仓概览</CardTitle>
            <CardDescription>当前组合持仓及收益情况</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-8 text-muted-foreground">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                加载中...
              </div>
            ) : (
              <>
                <div className="grid grid-cols-3 gap-4 mb-6">
                  <Card>
                    <CardContent className="pt-6">
                      <div className="text-2xl font-bold">{formatCurrency(totalMarketValue)}</div>
                      <p className="text-sm text-muted-foreground">总市值</p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="pt-6">
                      <div className="text-2xl font-bold">{formatCurrency(totalCost)}</div>
                      <p className="text-sm text-muted-foreground">总成本</p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="pt-6">
                      <div className={`text-2xl font-bold ${totalProfitLoss >= 0 ? "text-green-600" : "text-red-600"}`}>
                        {formatCurrency(totalProfitLoss)}
                      </div>
                      <p className="text-sm text-muted-foreground">总收益</p>
                    </CardContent>
                  </Card>
                </div>

                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>产品代码</TableHead>
                      <TableHead>产品名称</TableHead>
                      <TableHead>市场</TableHead>
                      <TableHead className="text-right">持仓份额</TableHead>
                      <TableHead className="text-right">成本价</TableHead>
                      <TableHead className="text-right">当前价</TableHead>
                      <TableHead className="text-right">市值</TableHead>
                      <TableHead className="text-right">盈亏</TableHead>
                      <TableHead className="text-right">收益率</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {positions.map((position) => (
                      <TableRow key={position.id}>
                        <TableCell className="font-medium">{position.product_code}</TableCell>
                        <TableCell>{position.product_name}</TableCell>
                        <TableCell>{position.market || "--"}</TableCell>
                        <TableCell className="text-right">
                          {position.shares ? formatNumber(position.shares) : "-"}
                        </TableCell>
                        <TableCell className="text-right">
                          {position.cost_price ? formatCurrency(position.cost_price) : "-"}
                        </TableCell>
                        <TableCell className="text-right">
                          {position.unit_price ? formatCurrency(position.unit_price) : "-"}
                        </TableCell>
                        <TableCell className="text-right">
                          {position.market_value ? formatCurrency(position.market_value) : "-"}
                        </TableCell>
                        <TableCell className="text-right">
                          {position.profit_loss !== undefined && position.profit_loss !== null ? (
                            <span className={position.profit_loss >= 0 ? "text-green-600" : "text-red-600"}>
                              {formatCurrency(position.profit_loss)}
                            </span>
                          ) : (
                            "-"
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          {position.profit_loss_percent !== undefined && position.profit_loss_percent !== null ? (
                            <span className={position.profit_loss_percent >= 0 ? "text-green-600" : "text-red-600"}>
                              {formatReturnRate(position.profit_loss_percent)}
                            </span>
                          ) : (
                            "-"
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                {positions.length === 0 && (
                  <div className="text-center text-muted-foreground py-8">
                    暂无持仓数据
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}