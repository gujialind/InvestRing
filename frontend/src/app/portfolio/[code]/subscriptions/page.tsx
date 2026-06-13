"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import MainLayout from "@/components/layout/MainLayout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
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
import { formatCurrency, formatNumber } from "@/lib/utils";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { subscriptionApi } from "@/lib/api";
import { Plus, ArrowLeft, CheckCircle, XCircle, Loader2, Pencil, Trash2 } from "lucide-react";
import Link from "next/link";
import { useSubscriptionList, useCreateSubscription, useConfirmSubscription, useCancelSubscription } from "@/hooks/useTrade";
import { useInvestorList } from "@/hooks/useInvestor";
import { usePortfolio } from "@/hooks/usePortfolio";
import type { Subscription } from "@/types/subscription";

export default function SubscriptionsPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const code = params.code as string;



  const { data, isLoading, refetch } = useSubscriptionList({ portfolio_code: code, page_size: 100 });
  const createSubscription = useCreateSubscription();
  const confirmSubscription = useConfirmSubscription();
  const cancelSubscription = useCancelSubscription();
  const { data: investorsData } = useInvestorList({ page_size: 100 });
  const { data: portfolio } = usePortfolio(code);

  const subscriptions = data?.items || [];
  const investors = investorsData?.items || [];

  const isDraft = portfolio?.status === "draft";

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [subType, setSubType] = useState<"subscribe" | "redeem">("subscribe");
  const [formData, setFormData] = useState({
    investor_code: "",
    amount: "",
    shares: "",
    apply_date: new Date().toISOString().split("T")[0],
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const data = {
      portfolio_code: code,
      investor_code: formData.investor_code,
      sub_type: subType,
      apply_date: formData.apply_date,
      ...(subType === "subscribe"
        ? { amount: parseFloat(formData.amount) }
        : { shares: parseFloat(formData.shares) }
      ),
    };
    createSubscription.mutate(data, {
      onSuccess: () => {
        setIsDialogOpen(false);
        setFormData({ investor_code: "", amount: "", shares: "", apply_date: new Date().toISOString().split("T")[0] });
        if (isDraft) {
          router.push(`/portfolio/${code}`);
        }
      },
    });
  };

  const handleConfirm = (id: number) => {
    if (confirm("确定要确认该申请吗？")) {
      confirmSubscription.mutate({ id });
    }
  };

  const handleCancel = (id: number) => {
    if (confirm("确定要取消该申请吗？")) {
      cancelSubscription.mutate(id);
    }
  };

  const deleteSubscriptionMutation = useMutation({
    mutationFn: (id: number) => subscriptionApi.delete(id),
    onSuccess: () => {
      alert("申购赎回事件删除成功\n\n建议前往快照管理页面重算相关日期的快照以保持数据一致性");
      queryClient.invalidateQueries({ queryKey: ["subscriptions", code] });
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail?.message || "删除失败";
      alert(`删除失败: ${message}`);
    },
  });

  const handleEdit = (sub: Subscription) => {
    alert("已确认的申购赎回事件不可直接修改，请先取消确认");
  };

  const handleDeleteClick = (id: number) => {
    if (confirm("删除后将影响后续快照数据，建议先取消确认再删除。是否继续？")) {
      deleteSubscriptionMutation.mutate(id);
    }
  };

  if (isLoading) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center h-[60vh]">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="space-y-6">
        {isDraft && (
          <Alert>
            <AlertDescription>
              首次申购将激活组合，初始净值固定为 1.0000
            </AlertDescription>
          </Alert>
        )}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href={`/portfolio/${code}`}>
              <Button variant="ghost" size="sm">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <div>
              <h1 className="text-3xl font-bold tracking-tight">申购赎回</h1>
              <p className="text-muted-foreground">组合代码: {code}</p>
            </div>
          </div>
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                {isDraft ? "首次申购激活" : "提交申请"}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{isDraft ? "首次申购激活" : "提交申请"}</DialogTitle>
                <DialogDescription>
                  {isDraft ? "提交首次申购以激活组合，初始净值固定为 1.0000" : "提交申购或赎回申请"}
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={handleSubmit}>
                <div className="space-y-4 py-4">
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant={subType === "subscribe" ? "default" : "outline"}
                      onClick={() => setSubType("subscribe")}
                      className="flex-1"
                    >
                      申购
                    </Button>
                    <Button
                      type="button"
                      variant={subType === "redeem" ? "default" : "outline"}
                      onClick={() => setSubType("redeem")}
                      className="flex-1"
                    >
                      赎回
                    </Button>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="investor_code">投资人</Label>
                    <select
                      id="investor_code"
                      value={formData.investor_code}
                      onChange={(e) => setFormData({ ...formData, investor_code: e.target.value })}
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                      required
                    >
                      <option value="">请选择投资人</option>
                      {investors.map((inv) => (
                        <option key={inv.code} value={inv.code}>{inv.name} ({inv.code})</option>
                      ))}
                    </select>
                  </div>
                  {subType === "subscribe" ? (
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
                    <Label htmlFor="apply_date">申请日期</Label>
                    <DatePicker
                      date={formData.apply_date ? new Date(formData.apply_date) : undefined}
                      onSelect={(date) => {
                        setFormData({ ...formData, apply_date: date ? date.toISOString().split("T")[0] : "" })
                      }}
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button type="submit" disabled={createSubscription.isPending}>
                    {createSubscription.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    提交申请
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>申请记录</CardTitle>
            <CardDescription>申购和赎回记录</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>投资人</TableHead>
                  <TableHead>类型</TableHead>
                  <TableHead className="text-right">金额/份额</TableHead>
                  <TableHead className="text-right">净值</TableHead>
                  <TableHead>申请日期</TableHead>
                  <TableHead>确认日期</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {subscriptions.map((sub) => (
                  <TableRow key={sub.id}>
                    <TableCell>{sub.investor_code}</TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        sub.sub_type === "subscribe"
                          ? "bg-blue-100 text-blue-800"
                          : "bg-orange-100 text-orange-800"
                      }`}>
                        {sub.sub_type === "subscribe" ? "申购" : "赎回"}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      {sub.amount ? formatCurrency(sub.amount) : formatNumber(sub.shares || 0)}
                    </TableCell>
                    <TableCell className="text-right">{sub.unit_price?.toFixed(4) || "--"}</TableCell>
                    <TableCell>{sub.apply_date}</TableCell>
                    <TableCell>{sub.confirm_date || "-"}</TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        sub.status === "confirmed"
                          ? "bg-green-100 text-green-800"
                          : sub.status === "pending"
                          ? "bg-yellow-100 text-yellow-800"
                          : "bg-gray-100 text-gray-800"
                      }`}>
                        {sub.status === "confirmed" ? "已确认" : sub.status === "pending" ? "待确认" : "已取消"}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      {sub.status === "pending" && (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleConfirm(sub.id)}
                            disabled={confirmSubscription.isPending}
                          >
                            <CheckCircle className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleCancel(sub.id)}
                            disabled={cancelSubscription.isPending}
                          >
                            <XCircle className="h-4 w-4" />
                          </Button>
                        </>
                      )}
                      {/* 新增：已确认交易的操作按钮 */}
                      {sub.status === "confirmed" && (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleEdit(sub)}
                            title="修改（需先取消确认）"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteClick(sub.id)}
                            title="删除（需先取消确认）"
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
            {subscriptions.length === 0 && (
              <div className="text-center text-muted-foreground py-8">
                暂无申请记录
              </div>
            )}
          </CardContent>
        </Card>

        
      </div>
    </MainLayout>
  );
}
