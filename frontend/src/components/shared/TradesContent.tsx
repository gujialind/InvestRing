"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
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
import { DatePicker } from "@/components/ui/date-picker";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
import { formatCurrency, formatNumber, formatMarketName } from "@/lib/utils";
import { Plus, ArrowLeft, CheckCircle, XCircle, Loader2, Pencil, Trash2, Undo } from "lucide-react";
import Link from "next/link";
import {
  useTradeList,
  useCreateTrade,
  useConfirmTrade,
  useCancelTrade,
  useUnconfirmTrade,
  useDeleteTrade,
} from "@/hooks/useTrade";
import { useProductList } from "@/hooks/useProduct";
import LoadingState from "@/components/shared/LoadingState";
import EmptyState from "@/components/shared/EmptyState";

interface TradesContentProps {
  /** 链接前缀：桌面 "/portfolio"，移动 "/m/portfolio" */
  basePath: string;
  variant?: "desktop" | "mobile";
}

type ConfirmState =
  | { action: "confirm"; id: number }
  | { action: "cancel"; id: number }
  | { action: "unconfirm"; id: number }
  | { action: "delete"; id: number }
  | null;

const CONFIRM_TEXT: Record<ConfirmState extends infer S ? S extends { action: string } ? S["action"] : never : never, { title: string; desc: string }> = {
  confirm: { title: "确认交易", desc: "确定要确认该交易吗？" },
  cancel: { title: "取消交易", desc: "确定要取消该交易吗？" },
  unconfirm: { title: "取消确认", desc: "取消后可以修改或删除。是否继续？" },
  delete: { title: "删除交易", desc: "删除后将影响后续快照数据，建议先取消确认再删除。是否继续？" },
};

/**
 * 调仓交易页内容（桌面/移动共用）。
 * 抽离自原 app/portfolio/[code]/trades/page.tsx，用 AlertDialog 替换原生 confirm/alert。
 * 桌面用表格；移动用可横向滚动表格（variant=mobile 时外层加 overflow-x-auto）。
 */
export default function TradesContent({ basePath, variant = "desktop" }: TradesContentProps) {
  const params = useParams();
  const code = params.code as string;

  const { data, isLoading } = useTradeList({ portfolio_code: code, page_size: 100 });
  const createTrade = useCreateTrade();
  const confirmTrade = useConfirmTrade();
  const cancelTrade = useCancelTrade();
  const unconfirmTrade = useUnconfirmTrade();
  const deleteTradeMutation = useDeleteTrade();
  const { data: productsData } = useProductList({ page_size: 100 });

  const trades = data?.items || [];
  const products = productsData?.items || [];

  const getProductName = (productCode: string, market?: string) => {
    const product = products.find((p) => p.code === productCode && p.market === market);
    return product?.name || productCode;
  };

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [tradeType, setTradeType] = useState<"buy" | "sell">("buy");
  const [formData, setFormData] = useState({
    product_code: "",
    market: "",
    shares: "",
    amount: "",
    price: "",
    trade_date: new Date().toISOString().split("T")[0],
  });
  const [confirmState, setConfirmState] = useState<ConfirmState>(null);
  // 编辑提示（原 alert 改为内部状态展示）
  const [editHint, setEditHint] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      portfolio_code: code,
      product_code: formData.product_code,
      market: formData.market || undefined,
      trade_type: tradeType,
      trade_date: formData.trade_date,
      price: formData.price ? parseFloat(formData.price) : undefined,
      ...(tradeType === "buy"
        ? { amount: parseFloat(formData.amount) }
        : { shares: parseFloat(formData.shares) }),
    };
    createTrade.mutate(payload, {
      onSuccess: () => {
        setIsDialogOpen(false);
        setFormData({ product_code: "", market: "", shares: "", amount: "", price: "", trade_date: new Date().toISOString().split("T")[0] });
      },
    });
  };

  const runConfirm = () => {
    if (!confirmState) return;
    const { action, id } = confirmState;
    if (action === "confirm") confirmTrade.mutate({ id });
    else if (action === "cancel") cancelTrade.mutate(id);
    else if (action === "unconfirm") unconfirmTrade.mutate(id);
    else if (action === "delete") deleteTradeMutation.mutate(id);
    setConfirmState(null);
  };

  if (isLoading) return <LoadingState />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href={`${basePath}/${code}`}>
            <Button variant="ghost" size="sm">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className={variant === "mobile" ? "text-2xl font-bold" : "text-3xl font-bold tracking-tight"}>
              调仓交易
            </h1>
            <p className="text-muted-foreground">组合代码: {code}</p>
          </div>
        </div>
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen} modal={false}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              提交交易
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>提交交易</DialogTitle>
              <DialogDescription>提交买入或卖出交易</DialogDescription>
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
                  <Label htmlFor="product_code">产品</Label>
                  <select
                    id="product_code"
                    value={formData.product_code}
                    onChange={(e) => {
                      const selected = products.find((p) => p.code === e.target.value);
                      setFormData({
                        ...formData,
                        product_code: e.target.value,
                        market: selected?.market || "",
                      });
                    }}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    required
                  >
                    <option value="">请选择产品</option>
                    {products.map((product) => (
                      <option key={`${product.code}-${product.market || "null"}`} value={product.code}>
                        {product.name} ({product.code})
                      </option>
                    ))}
                  </select>
                </div>
                {tradeType === "buy" ? (
                  <div className="space-y-2">
                    <Label htmlFor="amount">金额（元）</Label>
                    <Input
                      id="amount"
                      type="number"
                      step="0.01"
                      value={formData.amount}
                      onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                      required
                    />
                  </div>
                ) : (
                  <div className="space-y-2">
                    <Label htmlFor="shares">份额</Label>
                    <Input
                      id="shares"
                      type="number"
                      step="0.01"
                      value={formData.shares}
                      onChange={(e) => setFormData({ ...formData, shares: e.target.value })}
                      required
                    />
                  </div>
                )}
                <div className="space-y-2">
                  <Label htmlFor="price">价格</Label>
                  <Input
                    id="price"
                    type="number"
                    step="0.0001"
                    value={formData.price}
                    onChange={(e) => setFormData({ ...formData, price: e.target.value })}
                    placeholder="可选，确认时填写"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="trade_date">交易日期</Label>
                  <DatePicker
                    date={formData.trade_date ? new Date(formData.trade_date) : undefined}
                    onSelect={(date) => {
                      setFormData({ ...formData, trade_date: date ? date.toISOString().split("T")[0] : "" });
                    }}
                  />
                </div>
              </div>
              <DialogFooter>
                <Button type="submit" disabled={createTrade.isPending}>
                  {createTrade.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  提交交易
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>交易记录</CardTitle>
          <CardDescription>买入和卖出记录</CardDescription>
        </CardHeader>
        <CardContent>
          <div className={variant === "mobile" ? "overflow-x-auto" : ""}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>产品</TableHead>
                  <TableHead>市场</TableHead>
                  <TableHead>类型</TableHead>
                  <TableHead className="text-right">金额/份额</TableHead>
                  <TableHead className="text-right">价格</TableHead>
                  <TableHead>交易日期</TableHead>
                  <TableHead>确认日期</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {trades.map((trade) => (
                  <TableRow key={trade.id}>
                    <TableCell>
                      <div>
                        <p className="font-medium">{getProductName(trade.product_code, trade.market)}</p>
                        <p className="text-sm text-muted-foreground">{trade.product_code}</p>
                      </div>
                    </TableCell>
                    <TableCell>{formatMarketName(trade.market)}</TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        trade.trade_type === "buy" ? "bg-blue-100 text-blue-800" : "bg-orange-100 text-orange-800"
                      }`}>
                        {trade.trade_type === "buy" ? "买入" : "卖出"}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      {trade.amount ? formatCurrency(trade.amount) : formatNumber(trade.shares || 0)}
                    </TableCell>
                    <TableCell className="text-right">{trade.price?.toFixed(4) || "--"}</TableCell>
                    <TableCell>{trade.trade_date}</TableCell>
                    <TableCell>{trade.confirm_date || "-"}</TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        trade.status === "confirmed"
                          ? "bg-green-100 text-green-800"
                          : trade.status === "pending"
                          ? "bg-yellow-100 text-yellow-800"
                          : "bg-gray-100 text-gray-800"
                      }`}>
                        {trade.status === "confirmed" ? "已确认" : trade.status === "pending" ? "待确认" : "已取消"}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      {trade.status === "pending" && (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setConfirmState({ action: "confirm", id: trade.id })}
                            disabled={confirmTrade.isPending}
                          >
                            <CheckCircle className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setConfirmState({ action: "cancel", id: trade.id })}
                            disabled={cancelTrade.isPending}
                          >
                            <XCircle className="h-4 w-4" />
                          </Button>
                        </>
                      )}
                      {trade.status === "confirmed" && (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setConfirmState({ action: "unconfirm", id: trade.id })}
                            title="取消确认"
                          >
                            <Undo className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => setEditHint(true)} title="修改">
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setConfirmState({ action: "delete", id: trade.id })}
                            title="删除"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          {trades.length === 0 && <EmptyState message="暂无交易记录" />}
        </CardContent>
      </Card>

      <AlertDialog open={!!confirmState} onOpenChange={(open) => !open && setConfirmState(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{confirmState ? CONFIRM_TEXT[confirmState.action].title : ""}</AlertDialogTitle>
            <AlertDialogDescription>{confirmState ? CONFIRM_TEXT[confirmState.action].desc : ""}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                runConfirm();
              }}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              确认
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={editHint} onOpenChange={setEditHint}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>无法直接修改</AlertDialogTitle>
            <AlertDialogDescription>
              请先点击「取消确认」按钮（↩️图标），将交易状态改为 pending 后再修改
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogAction>知道了</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
