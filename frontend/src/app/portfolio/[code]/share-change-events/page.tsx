"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
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
import { DatePicker } from "@/components/ui/date-picker";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { formatCurrency, formatNumber, toDateOnly, parseDateOnly } from "@/lib/utils";
import { Plus, ArrowLeft, Loader2, CheckCircle, XCircle } from "lucide-react";
import Link from "next/link";
import { shareChangeEventApi, ShareChangeEvent, ShareChangeEventCreate, getErrorMessage } from "@/lib/api";
import { EventType } from "@/types/common";
import { useUIStore } from "@/stores/uiStore";
import { useQuery } from "@tanstack/react-query";

const EVENT_TYPE_LABELS: Record<EventType, string> = {
  cash_dividend: "现金分红",
  reinvest_dividend: "分红再投资",
  share_split: "份额拆分",
  share_merge: "份额合并",
  bonus_share: "红股送股",
  forced_adjustment: "强制调整",
};

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  confirmed: "bg-green-100 text-green-800",
  cancelled: "bg-gray-100 text-gray-800",
};

export default function ShareChangeEventsPage() {
  const params = useParams();
  const code = params.code as string;
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [formData, setFormData] = useState<ShareChangeEventCreate>({
    portfolio_code: code,
    event_type: "cash_dividend",
    event_date: toDateOnly(new Date()),
    entitlement_date: toDateOnly(new Date()),
    product_code: "",
    market: "",
    div_cash: 0,
    reinvest_nav: 0,
    ratio: 0,
    shares_change: 0,
    cash_change: 0,
    notes: "",
  });

  // 查询份额变动事件列表
  const { data: eventsData, isLoading } = useQuery({
    queryKey: ["shareChangeEvents", code],
    queryFn: () => shareChangeEventApi.list({ portfolio_code: code, page_size: 100 }),
  });

  const events = eventsData?.items || [];

  // 创建事件
  const createEvent = useMutation({
    mutationFn: shareChangeEventApi.create,
    onSuccess: () => {
      addToast({
        type: "success",
        title: "创建成功",
        message: "份额变动事件已创建",
      });
      setIsDialogOpen(false);
      resetForm();
      queryClient.invalidateQueries({ queryKey: ["shareChangeEvents", code] });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "创建失败",
        message: getErrorMessage(error, "请检查输入数据后重试"),
      });
    },
  });

  // 确认事件
  const confirmEvent = useMutation({
    mutationFn: shareChangeEventApi.confirm,
    onSuccess: () => {
      addToast({
        type: "success",
        title: "确认成功",
        message: "份额变动事件已确认",
      });
      queryClient.invalidateQueries({ queryKey: ["shareChangeEvents", code] });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "确认失败",
        message: getErrorMessage(error, "请稍后重试"),
      });
    },
  });

  // 取消事件
  const cancelEvent = useMutation({
    mutationFn: shareChangeEventApi.cancel,
    onSuccess: () => {
      addToast({
        type: "success",
        title: "取消成功",
        message: "份额变动事件已取消",
      });
      queryClient.invalidateQueries({ queryKey: ["shareChangeEvents", code] });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "取消失败",
        message: getErrorMessage(error, "请稍后重试"),
      });
    },
  });

  const resetForm = () => {
    setFormData({
      portfolio_code: code,
      event_type: "cash_dividend",
      event_date: toDateOnly(new Date()),
      entitlement_date: toDateOnly(new Date()),
      product_code: "",
      market: "",
      div_cash: 0,
      reinvest_nav: 0,
      ratio: 0,
      shares_change: 0,
      cash_change: 0,
      notes: "",
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.product_code) {
      addToast({
        type: "error",
        title: "表单校验失败",
        message: "请填写产品代码",
      });
      return;
    }

    createEvent.mutate(formData);
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
              <h1 className="text-3xl font-bold tracking-tight">份额变动事件</h1>
              <p className="text-muted-foreground">组合代码: {code}</p>
            </div>
          </div>
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen} modal={false}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                新建事件
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>新建份额变动事件</DialogTitle>
                <DialogDescription>
                  记录基金分红、拆分、合并等份额变动事件
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={handleSubmit}>
                <div className="space-y-4 py-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="event_type">事件类型</Label>
                      <Select
                        value={formData.event_type}
                        onValueChange={(value) => setFormData({ ...formData, event_type: value as EventType })}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {Object.entries(EVENT_TYPE_LABELS).map(([key, label]) => (
                            <SelectItem key={key} value={key}>
                              {label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
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
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="event_date">事件日期</Label>
                      <DatePicker
                        date={parseDateOnly(formData.event_date)}
                        onSelect={(date) => {
                          setFormData({ ...formData, event_date: toDateOnly(date) })
                        }}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="entitlement_date">权益登记日</Label>
                      <DatePicker
                        date={parseDateOnly(formData.entitlement_date)}
                        onSelect={(date) => {
                          setFormData({ ...formData, entitlement_date: toDateOnly(date) })
                        }}
                      />
                    </div>
                  </div>

                  {/* 根据事件类型显示不同字段 */}
                  {(formData.event_type === "cash_dividend" || formData.event_type === "reinvest_dividend") && (
                    <>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="div_cash">每份分红金额（元）</Label>
                          <Input
                            id="div_cash"
                            type="number"
                            step="0.0001"
                            value={formData.div_cash}
                            onChange={(e) => setFormData({ ...formData, div_cash: parseFloat(e.target.value) || 0 })}
                          />
                        </div>
                        {formData.event_type === "reinvest_dividend" && (
                          <div className="space-y-2">
                            <Label htmlFor="reinvest_nav">再投资净值</Label>
                            <Input
                              id="reinvest_nav"
                              type="number"
                              step="0.0001"
                              value={formData.reinvest_nav}
                              onChange={(e) => setFormData({ ...formData, reinvest_nav: parseFloat(e.target.value) || 0 })}
                            />
                          </div>
                        )}
                      </div>
                    </>
                  )}

                  {(formData.event_type === "share_split" || formData.event_type === "share_merge" || formData.event_type === "bonus_share") && (
                    <div className="space-y-2">
                      <Label htmlFor="ratio">比例</Label>
                      <Input
                        id="ratio"
                        type="number"
                        step="0.0001"
                        value={formData.ratio}
                        onChange={(e) => setFormData({ ...formData, ratio: parseFloat(e.target.value) || 0 })}
                        placeholder="如：拆分比例 2.0 表示1份变2份"
                      />
                    </div>
                  )}

                  {formData.event_type === "forced_adjustment" && (
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="shares_change">份额变化</Label>
                        <Input
                          id="shares_change"
                          type="number"
                          step="0.0001"
                          value={formData.shares_change}
                          onChange={(e) => setFormData({ ...formData, shares_change: parseFloat(e.target.value) || 0 })}
                          placeholder="正数增加，负数减少"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="cash_change">现金变化</Label>
                        <Input
                          id="cash_change"
                          type="number"
                          step="0.01"
                          value={formData.cash_change}
                          onChange={(e) => setFormData({ ...formData, cash_change: parseFloat(e.target.value) || 0 })}
                          placeholder="正数增加，负数减少"
                        />
                      </div>
                    </div>
                  )}

                  <div className="space-y-2">
                    <Label htmlFor="notes">备注</Label>
                    <Input
                      id="notes"
                      value={formData.notes}
                      onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                      placeholder="可选"
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setIsDialogOpen(false)}>
                    取消
                  </Button>
                  <Button type="submit" disabled={createEvent.isPending}>
                    {createEvent.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    创建
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>事件列表</CardTitle>
            <CardDescription>查看和管理份额变动事件</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-8 text-muted-foreground">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                加载中...
              </div>
            ) : (
              <>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>事件类型</TableHead>
                      <TableHead>产品代码</TableHead>
                      <TableHead>事件日期</TableHead>
                      <TableHead>权益登记日</TableHead>
                      <TableHead className="text-right">份额变化</TableHead>
                      <TableHead className="text-right">现金变化</TableHead>
                      <TableHead>状态</TableHead>
                      <TableHead>操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {events.map((event) => (
                      <TableRow key={event.id}>
                        <TableCell>{EVENT_TYPE_LABELS[event.event_type] || event.event_type}</TableCell>
                        <TableCell>{event.product_code || "--"}</TableCell>
                        <TableCell>{event.event_date}</TableCell>
                        <TableCell>{event.entitlement_date}</TableCell>
                        <TableCell className="text-right">
                          {event.shares_change ? formatNumber(event.shares_change) : "--"}
                        </TableCell>
                        <TableCell className="text-right">
                          {event.cash_change ? formatCurrency(event.cash_change) : "--"}
                        </TableCell>
                        <TableCell>
                          <Badge className={STATUS_COLORS[event.status] || ""}>
                            {event.status === "pending" ? "待确认" : event.status === "confirmed" ? "已确认" : "已取消"}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            {event.status === "pending" && (
                              <>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => confirmEvent.mutate(event.id)}
                                  disabled={confirmEvent.isPending}
                                >
                                  <CheckCircle className="h-4 w-4 text-green-600" />
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => cancelEvent.mutate(event.id)}
                                  disabled={cancelEvent.isPending}
                                >
                                  <XCircle className="h-4 w-4 text-red-600" />
                                </Button>
                              </>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                {events.length === 0 && (
                  <div className="text-center text-muted-foreground py-8">
                    暂无份额变动事件
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
