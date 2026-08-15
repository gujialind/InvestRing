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

  const label = value
    ? (() => {
        const name = nameCache.get(selectionKey(value));
        return name ? `${name} (${value.code})` : value.code;
      })()
    : placeholder;

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
          <span className={cn("truncate", !value && "text-muted-foreground")}>{label}</span>
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
              return (
                <div
                  key={selectionKey(s)}
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
                  <span className="min-w-0 flex-1 truncate text-sm">
                    {p.name} ({p.code})
                    <span className="text-muted-foreground"> · {formatMarketName(s.market)}</span>
                  </span>
                </div>
              );
            })
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
