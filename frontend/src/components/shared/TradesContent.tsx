"use client";

import { Fragment, useMemo, useState } from "react";
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
import { DateRangePicker } from "@/components/ui/date-range-picker";
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
import { formatCurrency, formatNumber, formatNav, formatMarketName, toDateOnly, parseDateOnly, getStatusBadgeVariant, cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { TRADE_DIRECTION_COLORS } from "@/lib/colors";
import { Plus, ArrowLeft, CheckCircle, XCircle, Loader2, Pencil, Trash2, Undo, Filter } from "lucide-react";
import Link from "next/link";
import type { DateRange } from "react-day-picker";
import { isSameDay, subYears } from "date-fns";
import { ApiException } from "@/lib/api";
import type { TradeListParams } from "@/lib/api";
import type { Trade, TradeCreate } from "@/types/trade";
import { cashOrphanLabel, cashSubMeta, groupTradeRows } from "@/lib/tradePairs";
import {
  useTradeList,
  useCreateTrade,
  useConfirmTrade,
  useCancelTrade,
  useUnconfirmTrade,
  useDeleteTrade,
} from "@/hooks/useTrade";
import { useProductList } from "@/hooks/useProduct";
import { usePlatformList } from "@/hooks/usePlatform";
import LoadingState from "@/components/shared/LoadingState";
import EmptyState from "@/components/shared/EmptyState";
import PaginationBar from "@/components/shared/PaginationBar";
import NameCodeCell from "@/components/shared/NameCodeCell";
import ProductFilterSelect from "@/components/shared/ProductFilterSelect";
import SearchableProductSelect from "@/components/shared/SearchableProductSelect";
import ProductFormDialog from "@/components/shared/ProductFormDialog";
import { ProductSelection } from "@/components/shared/ProductFilterDialog";

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

/** 默认交易日期区间 = 快捷项「近1年」（#126 决策⑤，区间语义与 DateRangePicker 快捷项一致） */
function defaultTradeRange(): DateRange {
  return { from: subYears(new Date(), 1), to: new Date() };
}

/** 与默认区间一致（isSameDay 双端比较）→ 视为「无筛选」默认态，用于重置按钮显隐与空态文案 */
function isDefaultTradeRange(range: DateRange | undefined): boolean {
  if (!range?.from || !range.to) return false;
  const d = defaultTradeRange();
  return !!d.from && !!d.to && isSameDay(range.from, d.from) && isSameDay(range.to, d.to);
}

/**
 * 调仓交易页内容（桌面/移动共用）。
 * 抽离自原 app/portfolio/[code]/trades/page.tsx，用 AlertDialog 替换原生 confirm/alert。
 * 桌面用表格；移动用可横向滚动表格（variant=mobile 时外层加 overflow-x-auto）。
 */
export default function TradesContent({ basePath, variant = "desktop" }: TradesContentProps) {
  const params = useParams();
  const code = params.code as string;

  // 筛选状态（#126 服务端筛选）：tradeRange 默认最近 1 年（决策⑤，惰性初始化避免每渲染重算）
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [tradeTypeFilter, setTradeTypeFilter] = useState<string | undefined>(undefined);
  // 产品多选筛选（#155）：undefined = 全部产品；元素为 {code, market}（market 可空串）
  const [productFilters, setProductFilters] = useState<ProductSelection[] | undefined>(undefined);
  const [platformFilter, setPlatformFilter] = useState<string | undefined>(undefined);
  const [tradeRange, setTradeRange] = useState<DateRange | undefined>(() => defaultTradeRange());
  const [confirmRange, setConfirmRange] = useState<DateRange | undefined>(undefined);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filterOpen, setFilterOpen] = useState(false);

  // 空筛选字段为 undefined，axios 不传参；产品多选拼 `code|market` 逗号分隔（market 段可空，
  // 如 `CASH|`），与后端 products 参数契约一致（#155，与 product_code/market 互斥不同传）
  const listParams: TradeListParams = {
    portfolio_code: code,
    page,
    page_size: pageSize,
    status: statusFilter,
    trade_type: tradeTypeFilter,
    products: productFilters?.length
      ? productFilters.map((p) => `${p.code}|${p.market}`).join(",")
      : undefined,
    platform_code: platformFilter,
    trade_date_start: tradeRange?.from ? toDateOnly(tradeRange.from) : undefined,
    trade_date_end: tradeRange?.to ? toDateOnly(tradeRange.to) : undefined,
    confirm_date_start: confirmRange?.from ? toDateOnly(confirmRange.from) : undefined,
    confirm_date_end: confirmRange?.to ? toDateOnly(confirmRange.to) : undefined,
  };
  const { data, isLoading, isFetching } = useTradeList(listParams);
  const createTrade = useCreateTrade();
  const confirmTrade = useConfirmTrade();
  const cancelTrade = useCancelTrade();
  const unconfirmTrade = useUnconfirmTrade();
  const deleteTradeMutation = useDeleteTrade();
  const { data: productsData } = useProductList({ page_size: 100 });
  const { data: platformsData } = usePlatformList({ page_size: 100 });

  const trades = data?.items || [];
  const total = data?.total ?? 0;
  const products = productsData?.items || [];
  const platforms = platformsData?.items || [];

  // 结对视图行（#126 决策⑧）：保持后端排序序，同组相邻时配对腿自然成对
  const tradeRows = groupTradeRows(trades);

  // 平台 name 映射（#124 模式）：平台列主次双行 + 现金子行「现金扣款/到账 · 平台名」复用
  const platformNameMap = useMemo(
    () => new Map((platformsData?.items ?? []).map((plat) => [plat.code, plat.name])),
    [platformsData?.items]
  );
  // 非默认筛选判定（默认集 = 仅 tradeRange 为最近 1 年）：驱动「重置」按钮显隐与空态文案
  const hasNonDefaultFilter =
    statusFilter !== undefined ||
    tradeTypeFilter !== undefined ||
    productFilters !== undefined ||
    platformFilter !== undefined ||
    confirmRange !== undefined ||
    tradeRange === undefined ||
    !isDefaultTradeRange(tradeRange);
  const activeFilterCount =
    (statusFilter ? 1 : 0) +
    (tradeTypeFilter ? 1 : 0) +
    (productFilters?.length ? 1 : 0) +
    (platformFilter ? 1 : 0) +
    (confirmRange ? 1 : 0) +
    (tradeRange === undefined || !isDefaultTradeRange(tradeRange) ? 1 : 0);

  const resetFilters = () => {
    setStatusFilter(undefined);
    setTradeTypeFilter(undefined);
    setProductFilters(undefined);
    setPlatformFilter(undefined);
    setTradeRange(defaultTradeRange());
    setConfirmRange(undefined);
    setPage(1);
  };

  const getProductName = (productCode: string, market?: string) => {
    const product = products.find((p) => p.code === productCode && p.market === market);
    return product?.name || productCode;
  };

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  // 提交交易表单内嵌「新增产品」弹窗（受控，创建成功后自动选中）
  const [productFormOpen, setProductFormOpen] = useState(false);
  const [tradeType, setTradeType] = useState<"buy" | "sell">("buy");
  const [formData, setFormData] = useState({
    product_code: "",
    market: "",
    platform_code: "",
    cash_platform_code: "",
    shares: "",
    amount: "",
    price: "",
    trade_date: toDateOnly(new Date()),
  });
  const [confirmState, setConfirmState] = useState<ConfirmState>(null);
  // 编辑提示（原 alert 改为内部状态展示）
  const [editHint, setEditHint] = useState(false);
  // 命中 DUPLICATE_TRADE 时暂存待重试的交易，由确认框引导 allow_duplicate 重试
  const [duplicateTrade, setDuplicateTrade] = useState<TradeCreate | null>(null);

  const resetTradeForm = () => {
    setIsDialogOpen(false);
    setFormData({ product_code: "", market: "", platform_code: "", cash_platform_code: "", shares: "", amount: "", price: "", trade_date: toDateOnly(new Date()) });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const payload: TradeCreate = {
      portfolio_code: code,
      product_code: formData.product_code,
      market: formData.market || undefined,
      platform_code: formData.platform_code || undefined,
      cash_platform_code: formData.cash_platform_code || undefined,
      trade_type: tradeType,
      trade_date: formData.trade_date,
      price: formData.price ? parseFloat(formData.price) : undefined,
      ...(tradeType === "buy"
        ? { amount: parseFloat(formData.amount) }
        : { shares: parseFloat(formData.shares) }),
    };
    createTrade.mutate(payload, {
      onSuccess: resetTradeForm,
      onError: (error: unknown) => {
        // 重复交易：弹确认框引导 allow_duplicate 重试（hook 层已抑制该错误码的 toast）
        if (error instanceof ApiException && error.code === "DUPLICATE_TRADE") {
          setDuplicateTrade(payload);
        }
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

  // 筛选栏控件（visual-spec §9）：顺序 = 交易日期区间 → 确认日期区间 → 状态 → 产品 → 平台 → 类型；
  // 控件统一 h-9，下拉全部走 ui/select（「全部 X」用 "all" 哨兵，Radix SelectItem 不允许空串值）；
  // 产品为 ProductFilterDialog 多选弹窗触发按钮（#155），outline 风格同筛选栏
  const rangeWidth = variant === "mobile" ? "h-9 w-full" : "h-9 w-[240px]";
  const selectWidth = variant === "mobile" ? "h-9 w-full" : "h-9 w-[150px]";
  const productSelectWidth = variant === "mobile" ? "h-9 w-full" : "h-9 w-[220px]";
  const filterControls = (
    <>
      <DateRangePicker
        value={tradeRange}
        onChange={(r) => {
          setTradeRange(r);
          setPage(1);
        }}
        placeholder="交易日期"
        numberOfMonths={variant === "mobile" ? 1 : 2}
        className={rangeWidth}
      />
      <DateRangePicker
        value={confirmRange}
        onChange={(r) => {
          setConfirmRange(r);
          setPage(1);
        }}
        placeholder="确认日期"
        numberOfMonths={variant === "mobile" ? 1 : 2}
        className={rangeWidth}
      />
      <Select
        value={statusFilter ?? "all"}
        onValueChange={(v) => {
          setStatusFilter(v === "all" ? undefined : v);
          setPage(1);
        }}
      >
        <SelectTrigger className={selectWidth}>
          <SelectValue placeholder="全部状态" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全部状态</SelectItem>
          <SelectItem value="pending">待确认</SelectItem>
          <SelectItem value="confirmed">已确认</SelectItem>
          <SelectItem value="cancelled">已取消</SelectItem>
        </SelectContent>
      </Select>
      <ProductFilterSelect
        variant={variant}
        value={productFilters ?? []}
        onChange={(selection) => {
          // 空选择归一为 undefined（= 全部产品），与非默认筛选判定口径一致
          setProductFilters(selection.length ? selection : undefined);
          setPage(1);
        }}
        className={productSelectWidth}
      />
      <Select
        value={platformFilter ?? "all"}
        onValueChange={(v) => {
          setPlatformFilter(v === "all" ? undefined : v);
          setPage(1);
        }}
      >
        <SelectTrigger className={selectWidth}>
          <SelectValue placeholder="全部平台" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全部平台</SelectItem>
          {platforms.map((plat) => (
            <SelectItem key={plat.code} value={plat.code}>
              {plat.name} ({plat.code})
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select
        value={tradeTypeFilter ?? "all"}
        onValueChange={(v) => {
          setTradeTypeFilter(v === "all" ? undefined : v);
          setPage(1);
        }}
      >
        <SelectTrigger className={selectWidth}>
          <SelectValue placeholder="全部类型" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全部类型</SelectItem>
          <SelectItem value="buy">买入</SelectItem>
          <SelectItem value="sell">卖出</SelectItem>
        </SelectContent>
      </Select>
      {hasNonDefaultFilter && (
        <Button variant="ghost" size="sm" className="h-9" onClick={resetFilters}>
          重置
        </Button>
      )}
    </>
  );

  // 主行（普通单行 / 结对主行共用）；结对主行去下边框使主+子视觉成组（规范 §8 结对行）
  const renderMainRow = (trade: Trade, isPairMain: boolean) => (
    <TableRow key={trade.id} className={isPairMain ? "border-b-0" : undefined}>
      <TableCell>
        {/* CASH 孤儿单行：产品列改显示业务来源（§5.8 简化口径）；结对主行/基金单行维持产品名+code 双行 */}
        {trade.product_code === "CASH" && !isPairMain ? (
          <span className="text-sm">{cashOrphanLabel(trade)}</span>
        ) : (
          <div>
            <p className="font-medium">{getProductName(trade.product_code, trade.market)}</p>
            <p className="text-xs text-muted-foreground">{trade.product_code}</p>
          </div>
        )}
      </TableCell>
      <TableCell>{formatMarketName(trade.market)}</TableCell>
      <TableCell>
        {trade.platform_code ? <NameCodeCell code={trade.platform_code} nameMap={platformNameMap} /> : "-"}
      </TableCell>
      <TableCell>
        {/* 方向标识无状态语义：neutral badge + 方向色圆点（lib/colors，#127） */}
        <Badge variant="neutral">
          <span
            className="mr-1.5 h-1.5 w-1.5 rounded-full"
            style={{ background: TRADE_DIRECTION_COLORS[trade.trade_type === "buy" ? "buy" : "sell"] }}
          />
          {trade.trade_type === "buy" ? "买入" : "卖出"}
        </Badge>
      </TableCell>
      <TableCell className="text-right">
        {trade.amount ? formatCurrency(trade.amount) : formatNumber(trade.shares || 0)}
      </TableCell>
      <TableCell className="text-right">{formatNav(trade.price)}</TableCell>
      <TableCell>{trade.trade_date}</TableCell>
      <TableCell>
        {/* 决策②：pending 的 confirm_date 是预计确认日，主次双行标注「预计」 */}
        {trade.confirm_date ? (
          trade.status === "pending" ? (
            <>
              <div className="text-sm">{trade.confirm_date}</div>
              <div className="text-xs text-muted-foreground">预计</div>
            </>
          ) : (
            trade.confirm_date
          )
        ) : (
          "-"
        )}
      </TableCell>
      <TableCell>
        <Badge variant={getStatusBadgeVariant(trade.status)}>
          {trade.status === "confirmed" ? "已确认" : trade.status === "pending" ? "待确认" : "已取消"}
        </Badge>
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
  );

  // 现金子行（规范 §8）：首列 pl-8、整行 bg-muted/50、内容 text-xs；金额 text-foreground 手工 +/- 前缀
  // （资金流向非涨跌语义，禁用 gain/loss token）；操作列空、不单独响应 hover
  const renderCashSubRow = (main: Trade, sub: Trade) => {
    const meta = cashSubMeta(main);
    const platformName = sub.platform_code ? platformNameMap.get(sub.platform_code) : undefined;
    return (
      <TableRow key={`cash-${sub.id}`} className="bg-muted/50 hover:bg-muted/50">
        <TableCell className="pl-8">
          <span className="text-xs text-muted-foreground">
            {meta.label}
            {platformName ? ` · ${platformName}` : ""}
          </span>
        </TableCell>
        <TableCell />
        <TableCell />
        <TableCell />
        <TableCell className="text-right">
          <span className="text-xs text-foreground">
            {meta.sign}
            {formatCurrency(sub.amount ?? 0)}
          </span>
        </TableCell>
        <TableCell />
        <TableCell />
        <TableCell />
        <TableCell />
        <TableCell className="text-right" />
      </TableRow>
    );
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
                  {/* 可搜索单选下拉（粒度 code|market，消除按 code 猜测市场的歧义）+ 新建入口 */}
                  <div className="flex gap-2">
                    <div className="min-w-0 flex-1">
                      <SearchableProductSelect
                        value={
                          formData.product_code
                            ? { code: formData.product_code, market: formData.market }
                            : null
                        }
                        onChange={(v) =>
                          setFormData({
                            ...formData,
                            product_code: v?.code ?? "",
                            market: v?.market ?? "",
                          })
                        }
                      />
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      className="h-10 w-10 shrink-0"
                      aria-label="新增产品"
                      title="新增产品"
                      onClick={() => setProductFormOpen(true)}
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="platform_code">交易平台</Label>
                  <select
                    id="platform_code"
                    value={formData.platform_code}
                    onChange={(e) => setFormData({ ...formData, platform_code: e.target.value })}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  >
                    <option value="">请选择平台</option>
                    {platforms.map((plat) => (
                      <option key={plat.code} value={plat.code}>
                        {plat.name} ({plat.code})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="cash_platform_code">
                    现金平台（{tradeType === "buy" ? "扣款" : "到账"}，可选）
                  </Label>
                  <select
                    id="cash_platform_code"
                    value={formData.cash_platform_code}
                    onChange={(e) => setFormData({ ...formData, cash_platform_code: e.target.value })}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  >
                    <option value="">同交易平台</option>
                    {platforms.map((plat) => (
                      <option key={plat.code} value={plat.code}>
                        {plat.name} ({plat.code})
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
                    date={parseDateOnly(formData.trade_date)}
                    onSelect={(date) => {
                      setFormData({ ...formData, trade_date: toDateOnly(date) });
                    }}
                  />
                </div>
              </div>
              <DialogFooter>
                <Button
                  type="submit"
                  disabled={createTrade.isPending || !formData.product_code}
                >
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
          {/* 筛选栏（规范 §9：表格卡片内顶部）；移动端为折叠面板 + 激活计数 Badge */}
          {variant === "mobile" ? (
            <div className="mb-3 space-y-2">
              <Button variant="outline" size="sm" className="h-9" onClick={() => setFilterOpen((v) => !v)}>
                <Filter className="mr-2 h-4 w-4" />
                筛选
                {activeFilterCount > 0 && (
                  <Badge variant="default" className="ml-2">
                    {activeFilterCount}
                  </Badge>
                )}
              </Button>
              {filterOpen && <div className="grid grid-cols-1 gap-2">{filterControls}</div>}
            </div>
          ) : (
            <div className="mb-3 flex flex-wrap items-center gap-2">{filterControls}</div>
          )}
          {/* 规范 §14：筛选/翻页局部刷新保留旧数据，表格半透明 + 右上角小 spinner */}
          <div className="relative">
            {isFetching && (
              <Loader2 className="absolute right-2 top-2 z-10 h-4 w-4 animate-spin text-muted-foreground" />
            )}
            <Table className={cn(isFetching && "opacity-50")}>
              <TableHeader>
                <TableRow>
                  <TableHead>产品</TableHead>
                  <TableHead>市场</TableHead>
                  <TableHead>平台</TableHead>
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
                {tradeRows.map((row) =>
                  row.kind === "pair" ? (
                    <Fragment key={row.main.id}>
                      {renderMainRow(row.main, true)}
                      {renderCashSubRow(row.main, row.sub)}
                    </Fragment>
                  ) : (
                    renderMainRow(row.trade, false)
                  )
                )}
              </TableBody>
            </Table>
          </div>
          {/* 空态：默认筛选集下为空 = 暂无记录；非默认筛选下为空 = 引导重置（规范 §8 变体②） */}
          {trades.length === 0 &&
            (hasNonDefaultFilter ? (
              <EmptyState
                message="无符合筛选条件的记录"
                action={
                  <Button variant="ghost" size="sm" onClick={resetFilters}>
                    重置筛选
                  </Button>
                }
              />
            ) : (
              <EmptyState message="暂无交易记录" />
            ))}
          <PaginationBar
            page={page}
            pageSize={pageSize}
            total={total}
            variant={variant}
            onPageChange={setPage}
            onPageSizeChange={(size) => {
              setPageSize(size);
              setPage(1);
            }}
          />
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

      {/* DUPLICATE_TRADE 确认重试 */}
      <AlertDialog open={!!duplicateTrade} onOpenChange={(open) => !open && setDuplicateTrade(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>检测到重复交易</AlertDialogTitle>
            <AlertDialogDescription>
              存在同组合/产品/方向/交易日且金额或份额相同的交易，是否仍要提交？
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (duplicateTrade) {
                  createTrade.mutate(
                    { ...duplicateTrade, allow_duplicate: true },
                    { onSuccess: resetTradeForm }
                  );
                }
                setDuplicateTrade(null);
              }}
            >
              仍要提交
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      {/* 新增产品：创建成功后自动选中（列表缓存失效由 hook 自带） */}
      <ProductFormDialog
        open={productFormOpen}
        onOpenChange={setProductFormOpen}
        onSuccess={(p) =>
          setFormData((prev) => ({ ...prev, product_code: p.code, market: p.market ?? "" }))
        }
      />
    </div>
  );
}
