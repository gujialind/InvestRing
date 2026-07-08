"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
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
import { formatCurrency, formatNumber, toDateOnly, parseDateOnly } from "@/lib/utils";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { subscriptionApi } from "@/lib/api";
import { Plus, ArrowLeft, CheckCircle, XCircle, Loader2, Pencil, Trash2, Undo } from "lucide-react";
import Link from "next/link";
import {
  useSubscriptionList,
  useCreateSubscription,
  useConfirmSubscription,
  useCancelSubscription,
  useUnconfirmSubscription,
} from "@/hooks/useTrade";
import { useInvestorList } from "@/hooks/useInvestor";
import { usePlatformList } from "@/hooks/usePlatform";
import { usePortfolio } from "@/hooks/usePortfolio";
import { useUIStore } from "@/stores/uiStore";
import LoadingState from "@/components/shared/LoadingState";
import EmptyState from "@/components/shared/EmptyState";

interface SubscriptionsContentProps {
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

const CONFIRM_TEXT: Record<"confirm" | "cancel" | "unconfirm" | "delete", { title: string; desc: string }> = {
  confirm: { title: "确认申请", desc: "确定要确认该申请吗？" },
  cancel: { title: "取消申请", desc: "确定要取消该申请吗？" },
  unconfirm: { title: "取消确认", desc: "取消后可以修改或删除。是否继续？" },
  delete: { title: "删除申请", desc: "删除后将影响后续快照数据，建议先取消确认再删除。是否继续？" },
};

/**
 * 申购赎回页内容（桌面/移动共用）。
 * 抽离自原 app/portfolio/[code]/subscriptions/page.tsx，
 * 用 AlertDialog 替换原生 confirm/alert，删除成功改用 toast 提示。
 */
export default function SubscriptionsContent({ basePath, variant = "desktop" }: SubscriptionsContentProps) {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);
  const code = params.code as string;

  const { data, isLoading } = useSubscriptionList({ portfolio_code: code, page_size: 100 });
  const createSubscription = useCreateSubscription();
  const confirmSubscription = useConfirmSubscription();
  const cancelSubscription = useCancelSubscription();
  const unconfirmSubscription = useUnconfirmSubscription();
  const { data: investorsData } = useInvestorList({ page_size: 100 });
  const { data: platformsData } = usePlatformList({ page_size: 100 });
  const { data: portfolio } = usePortfolio(code);

  const subscriptions = data?.items || [];
  const investors = investorsData?.items || [];
  const platforms = platformsData?.items || [];
  const isDraft = portfolio?.status === "draft";

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [subType, setSubType] = useState<"subscribe" | "redeem">("subscribe");
  const [formData, setFormData] = useState({
    investor_code: "",
    platform_code: "",
    amount: "",
    shares: "",
    apply_date: toDateOnly(new Date()),
  });
  const [confirmState, setConfirmState] = useState<ConfirmState>(null);
  const [editHint, setEditHint] = useState(false);

  const deleteSubscriptionMutation = useMutation({
    mutationFn: (id: number) => subscriptionApi.delete(id),
    onSuccess: () => {
      addToast({
        type: "success",
        title: "删除成功",
        message: "建议前往快照管理页面重算相关日期的快照以保持数据一致性",
      });
      queryClient.invalidateQueries({ queryKey: ["subscriptions", code] });
    },
    onError: (error: unknown) => {
      const e = error as { response?: { data?: { detail?: { message?: string } } }; message?: string };
      const message = e.response?.data?.detail?.message || "删除失败";
      addToast({ type: "error", title: "删除失败", message });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      portfolio_code: code,
      investor_code: formData.investor_code,
      platform_code: formData.platform_code,
      sub_type: subType,
      apply_date: formData.apply_date,
      ...(subType === "subscribe" ? { amount: parseFloat(formData.amount) } : { shares: parseFloat(formData.shares) }),
    };
    createSubscription.mutate(payload, {
      onSuccess: () => {
        setIsDialogOpen(false);
        setFormData({ investor_code: "", platform_code: "", amount: "", shares: "", apply_date: toDateOnly(new Date()) });
        if (isDraft) router.push(`${basePath}/${code}`);
      },
    });
  };

  const runConfirm = () => {
    if (!confirmState) return;
    const { action, id } = confirmState;
    if (action === "confirm") confirmSubscription.mutate({ id });
    else if (action === "cancel") cancelSubscription.mutate(id);
    else if (action === "unconfirm") unconfirmSubscription.mutate(id);
    else if (action === "delete") deleteSubscriptionMutation.mutate(id);
    setConfirmState(null);
  };

  if (isLoading) return <LoadingState />;

  return (
    <div className="space-y-6">
      {isDraft && (
        <Alert>
          <AlertDescription>首次申购将激活组合，初始净值固定为 1.0000</AlertDescription>
        </Alert>
      )}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href={`${basePath}/${code}`}>
            <Button variant="ghost" size="sm">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className={variant === "mobile" ? "text-2xl font-bold" : "text-3xl font-bold tracking-tight"}>
              申购赎回
            </h1>
            <p className="text-muted-foreground">组合代码: {code}</p>
          </div>
        </div>
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen} modal={false}>
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
                      <option key={inv.code} value={inv.code}>
                        {inv.name} ({inv.code})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="platform_code">交易平台</Label>
                  <select
                    id="platform_code"
                    value={formData.platform_code}
                    onChange={(e) => setFormData({ ...formData, platform_code: e.target.value })}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    required
                  >
                    <option value="">请选择平台</option>
                    {platforms.map((plat) => (
                      <option key={plat.code} value={plat.code}>
                        {plat.name} ({plat.code})
                      </option>
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
                    date={parseDateOnly(formData.apply_date)}
                    onSelect={(date) => {
                      setFormData({ ...formData, apply_date: toDateOnly(date) });
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
          <div className={variant === "mobile" ? "overflow-x-auto" : ""}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>投资人</TableHead>
                  <TableHead>平台</TableHead>
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
                    <TableCell>{sub.platform_code || "-"}</TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        sub.sub_type === "subscribe" ? "bg-blue-100 text-blue-800" : "bg-orange-100 text-orange-800"
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
                            onClick={() => setConfirmState({ action: "confirm", id: sub.id })}
                            disabled={confirmSubscription.isPending}
                          >
                            <CheckCircle className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setConfirmState({ action: "cancel", id: sub.id })}
                            disabled={cancelSubscription.isPending}
                          >
                            <XCircle className="h-4 w-4" />
                          </Button>
                        </>
                      )}
                      {sub.status === "confirmed" && (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setConfirmState({ action: "unconfirm", id: sub.id })}
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
                            onClick={() => setConfirmState({ action: "delete", id: sub.id })}
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
          {subscriptions.length === 0 && <EmptyState message="暂无申请记录" />}
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
              请先点击「取消确认」按钮（↩️图标），将申请状态改为 pending 后再修改
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
