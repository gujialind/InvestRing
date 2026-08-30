"use client";

import { useEffect, useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Check, ChevronDown, Loader2 } from "lucide-react";
import { useProductList } from "@/hooks/useProduct";
import { cn, formatMarketName } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { ProductSelection } from "@/components/shared/ProductFilterDialog";

interface SearchableProductSelectProps {
  /** 单选；null = 未选 */
  value: ProductSelection | null;
  onChange: (v: ProductSelection | null) => void;
  placeholder?: string;
  /** 触发按钮 id，供外层 Label htmlFor 关联（可访问性） */
  id?: string;
}

/**
 * 表单单选可搜索下拉（issue #162，提交交易表单）：h-10 触发按钮 + Popover
 * 关键词防抖搜索 + 点选即回传并关闭。选项粒度 code|market（LOF 一码多市场分行）。
 * 市场标识（#259）：选项行三段式——名称可截断 / (code) 独立不截断 / 尾部市场
 * Badge（market 为空不渲染），行挂完整 title；选中回显「名称 (code) · 市场名」，
 * 名称截断、后缀不截断，触发按钮挂 title。E2E 定位：product-option + data-code/data-market。
 */
export default function SearchableProductSelect({
  value,
  onChange,
  placeholder = "请选择产品",
  id,
}: SearchableProductSelectProps) {
  const [open, setOpen] = useState(false);
  // 懒加载（#165）：首次打开后才挂产品查询；sticky 不回落，避免关闭后缓存丢弃
  const [hasOpened, setHasOpened] = useState(false);

  // 关键字防抖 300ms（规范 §9 文本输入类）
  const [keywordInput, setKeywordInput] = useState("");
  const [keyword, setKeyword] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setKeyword(keywordInput.trim()), 300);
    return () => clearTimeout(timer);
  }, [keywordInput]);

  const { data, isLoading, isFetching } = useProductList(
    { page_size: 50, keyword: keyword || undefined },
    { enabled: hasOpened }
  );
  const items = useMemo(() => data?.items ?? [], [data?.items]);

  // 名称缓存：选中项回显 name (code)；name 仅来自当前/历史结果集，缺失时回退 code
  const nameByKey = useMemo(() => {
    const map = new Map<string, string>();
    for (const p of items) map.set(`${p.code}|${p.market ?? ""}`, p.name);
    return map;
  }, [items]);
  const [nameCache, setNameCache] = useState<Map<string, string>>(new Map());
  useEffect(() => {
    setNameCache((prev) => {
      let changed = false;
      const next = new Map(prev);
      for (const [k, v] of nameByKey) {
        if (next.get(k) !== v) {
          next.set(k, v);
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [nameByKey]);

  const selectionKey = (s: ProductSelection) => `${s.code}|${s.market}`;
  const isSelected = (s: ProductSelection) =>
    !!value && value.code === s.code && value.market === s.market;

  // 选中回显（#259）：「名称 (code)」基础标签 + 可选「 · 市场名」后缀；
  // market 为空不拼后缀（无 `· --` 残留）；名称部分 truncate、后缀 shrink-0，
  // 触发按钮 span 挂 title 全文本供悬停查看被截断部分
  const baseLabel = value
    ? (() => {
        const name = nameCache.get(selectionKey(value));
        return name ? `${name} (${value.code})` : value.code;
      })()
    : placeholder;
  const marketSuffix = value?.market ? formatMarketName(value.market) : "";
  const fullLabel = marketSuffix ? `${baseLabel} · ${marketSuffix}` : baseLabel;

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) setHasOpened(true);
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          id={id}
          className="flex h-10 w-full items-center justify-between gap-2 rounded-md border border-input bg-background px-3 py-2 text-left text-sm font-normal ring-offset-background transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <span
            className={cn("flex min-w-0 flex-1 items-center", !value && "text-muted-foreground")}
            title={value ? fullLabel : undefined}
          >
            <span className="min-w-0 truncate">{baseLabel}</span>
            {marketSuffix && <span className="shrink-0">{` · ${marketSuffix}`}</span>}
          </span>
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 p-0">
        <div className="relative border-b p-2">
          {isFetching && (
            <Loader2 className="absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted-foreground" />
          )}
          <Input
            value={keywordInput}
            onChange={(e) => setKeywordInput(e.target.value)}
            placeholder="搜索产品代码/名称"
            className="h-8"
          />
        </div>
        <div className="max-h-64 overflow-y-auto p-1">
          {isLoading ? (
            <div className="flex items-center justify-center py-6">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : items.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">无符合条件的产品</p>
          ) : (
            items.map((p) => {
              const s = { code: p.code, market: p.market ?? "" };
              // 市场标识（#259）：尾部独立徽章，market 为空不渲染；悬停 title 给出
              // 完整「名称 (code) · 市场」，长名称截断不丢信息
              const marketName = s.market ? formatMarketName(s.market) : "";
              return (
                <div
                  key={selectionKey(s)}
                  data-testid="product-option"
                  data-code={p.code}
                  data-market={s.market}
                  title={marketName ? `${p.name} (${p.code}) · ${marketName}` : `${p.name} (${p.code})`}
                  className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 hover:bg-muted"
                  onClick={() => {
                    onChange(s);
                    setOpen(false);
                  }}
                >
                  <Check
                    className={cn(
                      "h-4 w-4 shrink-0",
                      isSelected(s) ? "opacity-100" : "opacity-0"
                    )}
                  />
                  <span className="min-w-0 flex-1 truncate text-sm">{p.name}</span>
                  <span className="shrink-0 text-sm text-muted-foreground">({p.code})</span>
                  {s.market && (
                    <Badge variant="neutral" className="shrink-0">
                      {marketName}
                    </Badge>
                  )}
                </div>
              );
            })
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
