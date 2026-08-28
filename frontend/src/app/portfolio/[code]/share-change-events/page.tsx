"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
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
import { formatCurrency, formatNumber, toDateOnly, parseDateOnly, getStatusBadgeVariant } from "@/lib/utils";
import { Plus, ArrowLeft, Loader2, CheckCircle, XCircle } from "lucide-react";
import Link from "next/link";
import { ShareChangeEventCreate, ApiException } from "@/lib/api";
import { platformApi } from "@/lib/api";
import { EventType } from "@/types/common";
import { useUIStore } from "@/stores/uiStore";
import { useQuery } from "@tanstack/react-query";
import {
  useShareChangeEventList,
  useCreateShareChangeEvent,
  useConfirmShareChangeEvent,
  useCancelShareChangeEvent,
} from "@/hooks/useShareChangeEvent";
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
import SearchablePlatformSelect from "@/components/shared/SearchablePlatformSelect";
import { useProductList } from "@/hooks/useProduct";
import { EVENT_TYPE_LABELS, EventConfirmDialog } from "./event-confirm-dialog";

const PLATFORM_LEVEL_TYPES: EventType[] = ["cash_dividend", "reinvest_dividend", "forced_adjustment"];

// 状态徽标统一走 Badge variant 语义映射（#127，visual-spec §1.3）
const STATUS_LABELS: Record<string, string> = {
  pending: "待确认",
  confirmed: "已确认",
  cancelled: "已取消",
};

export default function ShareChangeEventsPage() {
  const params = useParams();
  const code = params.code as string;
  const addToast = useUIStore((state) => state.addToast);

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [formData, setFormData] = useState<ShareChangeEventCreate>({
    portfolio_code: code,
    event_type: "cash_dividend",
    ex_date: toDateOnly(new Date()),
    entitlement_date: toDateOnly(new Date()),
    platform_code: "",
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
  const { data: eventsData, isLoading } = useShareChangeEventList(code);

  // 查询平台列表
  const { data: platformsData } = useQuery({
    queryKey: ["platforms"],
    queryFn: () => platformApi.list({ page_size: 100 }),
  });

  // 产品列表（#248）：仅用于确认弹窗的「产品名（代码）」展示，复用缓存不新增页面依赖
  const { data: productsData } = useProductList({ page_size: 100 });

  const platforms = platformsData?.items || [];

  const events = eventsData?.items || [];

  // #248 确认信息核对弹窗：确认按钮先开弹窗，弹窗内二次点击才发起确认
  const [confirmEventId, setConfirmEventId] = useState<number | null>(null);
  const confirmingEvent = events.find((e) => e.id === confirmEventId) ?? null;
  const productNameMap = useMemo(
    () => new Map((productsData?.items ?? []).map((p) => [p.code, p.name])),
    [productsData?.items]
  );
  const platformNameMap = useMemo(
    () => new Map((platformsData?.items ?? []).map((plat) => [plat.code, plat.name])),
    [platformsData?.items]
  );

  // 创建/确认/取消走统一 hooks
  const createEvent = useCreateShareChangeEvent(code);
  const confirmEvent = useConfirmShareChangeEvent(code);
  const cancelEvent = useCancelShareChangeEvent(code);
  // 命中 PLATFORM_NOT_COVERED 时暂存待强制提交的数据，由确认框引导 force_cover 重试
  const [forceCoverData, setForceCoverData] = useState<ShareChangeEventCreate | null>(null);
  const [forceCoverMessage, setForceCoverMessage] = useState("");

  const resetForm = () => {
    setFormData({
      portfolio_code: code,
      event_type: "cash_dividend",
      ex_date: toDateOnly(new Date()),
      entitlement_date: toDateOnly(new Date()),
      platform_code: "",
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

  const submitCreate = (data: ShareChangeEventCreate, forceCover = false) => {
    createEvent.mutate(
      { data, forceCover },
      {
        onSuccess: () => {
          setIsDialogOpen(false);
          resetForm();
        },
        onError: (error: unknown) => {
          // 平台覆盖不全：弹确认框引导 force_cover 强制提交
          if (!forceCover && error instanceof ApiException && error.code === "PLATFORM_NOT_COVERED") {
            setForceCoverData(data);
            setForceCoverMessage(error.message);
          }
        },
      }
    );
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

    if (PLATFORM_LEVEL_TYPES.includes(formData.event_type) && !formData.platform_code) {
      // 与申赎 R1 同口径：自定义平台控件无原生 required，须手动拦截
      addToast({
        type: "error",
        title: "表单校验失败",
        message: "请选择平台",
      });
      return;
    }

    submitCreate(formData);
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

                  {/* 平台选择器：仅平台级事件显示 */}
                  {PLATFORM_LEVEL_TYPES.includes(formData.event_type) && (
                    <div className="space-y-2">
                      <Label htmlFor="platform_code">平台</Label>
                      <SearchablePlatformSelect
                        platforms={platforms}
                        value={formData.platform_code || null}
                        onChange={(v) => setFormData({ ...formData, platform_code: v ?? "" })}
                        placeholder="选择平台"
                        id="platform_code"
                      />
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="ex_date">除息日</Label>
                      <DatePicker
                        date={parseDateOnly(formData.ex_date)}
                        onSelect={(date) => {
                          setFormData({ ...formData, ex_date: toDateOnly(date) })
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
                          step="0.01"
                          value={formData.shares_change}
                          onChange={(e) => setFormData({ ...formData, shares_change: parseFloat(e.target.value) || 0 })}
                          placeholder="正数增加，负数减少（份额 2 位小数）"
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
                      <TableHead>平台</TableHead>
                      <TableHead>除息日</TableHead>
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
                        <TableCell>{event.platform_code || "全部"}</TableCell>
                        <TableCell>{event.ex_date}</TableCell>
                        <TableCell>{event.entitlement_date}</TableCell>
                        <TableCell className="text-right">
                          {event.shares_change ? formatNumber(event.shares_change) : "--"}
                        </TableCell>
                        <TableCell className="text-right">
                          {event.cash_change ? formatCurrency(event.cash_change) : "--"}
                        </TableCell>
                        <TableCell>
                          <Badge variant={getStatusBadgeVariant(event.status)}>
                            {STATUS_LABELS[event.status] || event.status}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            {event.status === "pending" && (
                              <>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => setConfirmEventId(event.id)}
                                >
                                  <CheckCircle className="h-4 w-4 text-success" />
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => cancelEvent.mutate(event.id)}
                                  disabled={cancelEvent.isPending}
                                >
                                  <XCircle className="h-4 w-4 text-destructive" />
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

      {/* #248：确认信息核对弹窗（事件字段均落库，无预览请求），弹窗内二次确认才发起请求 */}
      <EventConfirmDialog
        open={confirmEventId !== null}
        onOpenChange={(open) => !open && setConfirmEventId(null)}
        event={confirmingEvent}
        productNameMap={productNameMap}
        platformNameMap={platformNameMap}
        isConfirming={confirmEvent.isPending}
        onConfirm={() => {
          if (confirmEventId === null) return;
          confirmEvent.mutate(confirmEventId, { onSuccess: () => setConfirmEventId(null) });
        }}
      />

      {/* PLATFORM_NOT_COVERED 强制提交确认 */}
      <AlertDialog open={!!forceCoverData} onOpenChange={(open) => !open && setForceCoverData(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>平台覆盖不完整</AlertDialogTitle>
            <AlertDialogDescription>
              {forceCoverMessage || "平台级事件未覆盖全部有持仓的平台。"}
              确定要忽略此检查强制提交吗？
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (forceCoverData) {
                  submitCreate(forceCoverData, true);
                }
                setForceCoverData(null);
              }}
            >
              强制提交
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </MainLayout>
  );
}
