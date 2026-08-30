"use client";

import { useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { Platform } from "@/types/platform";

interface SearchablePlatformSelectProps {
  /** 平台全量列表（调用方已加载；组件不内部 fetch） */
  platforms: Platform[];
  /** 选中平台 code；null = 未选/选中前置特殊项 */
  value: string | null;
  /** 点选平台回传 code；点选前置特殊项回传 null */
  onChange: (code: string | null) => void;
  /** 前置特殊项文案（固定置顶、不参与搜索过滤），如「全部平台」「同交易平台」；
   *  value === null 时触发按钮以正常前景色回显该文案 */
  specialOptionLabel?: string;
  /** 无 specialOptionLabel 且 value === null 时的占位文案（muted 色），默认「请选择平台」 */
  placeholder?: string;
  /** 逐选项禁用谓词（现金转移互斥）：禁用项可见但不可点 */
  isOptionDisabled?: (platform: Platform) => boolean;
  /** 触发按钮附加 className（尺寸档：筛选栏传 h-9 档、表单默认 h-10；cn+twMerge 后者覆盖前者） */
  className?: string;
  /** 触发按钮 id，供外层 Label htmlFor 关联（可访问性） */
  id?: string;
}

/**
 * 平台单选可搜索下拉：复刻 SearchableProductSelect（#162）交互外壳，
 * 数据流刻意不同——平台全量列表由调用方持有经 props 传入，组件不内部 fetch；
 * 本地客户端过滤（name/code 大小写不敏感），无防抖、无名称缓存。
 * 前置特殊项（全部平台/同交易平台）固定置顶不参与过滤，点选回传 null。
 */
export default function SearchablePlatformSelect({
  platforms,
  value,
  onChange,
  specialOptionLabel,
  placeholder = "请选择平台",
  isOptionDisabled,
  className,
  id,
}: SearchablePlatformSelectProps) {
  const [open, setOpen] = useState(false);
  const [keyword, setKeyword] = useState("");

  const kw = keyword.trim().toLowerCase();
  const filtered = useMemo(
    () =>
      kw
        ? platforms.filter(
            (p) =>
              p.name.toLowerCase().includes(kw) ||
              p.code.toLowerCase().includes(kw)
          )
        : platforms,
    [platforms, kw]
  );

  // 触发按钮回显：选中平台 → name (code)；列表找不到（加载中/异常兜底）→ code 本身；
  // value === null → 特殊项文案（正常色）或 placeholder（muted 色）
  const selected = value ? platforms.find((p) => p.code === value) : undefined;
  const label = selected
    ? `${selected.name} (${selected.code})`
    : value ?? specialOptionLabel ?? placeholder;
  const labelMuted = !selected && !value && !specialOptionLabel;

  const pick = (code: string | null) => {
    onChange(code);
    setOpen(false);
    // 编程式 setOpen(false) 不触发 Radix onOpenChange，须在此重置搜索词，
    // 否则下次打开仍是上次过滤后的列表
    setKeyword("");
  };

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) setKeyword(""); // 关闭即重置搜索词，每次打开全量选项
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          id={id}
          data-testid="platform-trigger"
          className={cn(
            "flex h-10 w-full items-center justify-between gap-2 rounded-md border border-input",
            "bg-background px-3 py-2 text-left text-sm font-normal ring-offset-background",
            "transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2",
            "focus-visible:ring-ring focus-visible:ring-offset-2",
            className
          )}
        >
          <span className={cn("truncate", labelMuted && "text-muted-foreground")}>{label}</span>
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
        </button>
      </PopoverTrigger>
      {/* #328：宽度跟随触发框（Radix 注入 trigger 宽度变量），min-w-56 保底窄触发框下搜索框可读 */}
      <PopoverContent align="start" className="w-[var(--radix-popover-trigger-width)] min-w-56 p-0">
        <div className="border-b p-2">
          <Input
            autoFocus
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="搜索平台名称/代码"
            className="h-8"
          />
        </div>
        <div className="max-h-64 overflow-y-auto p-1">
          {specialOptionLabel && (
            <div
              data-testid="platform-special-option"
              className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 hover:bg-muted"
              onClick={() => pick(null)}
            >
              <Check
                className={cn(
                  "h-4 w-4 shrink-0",
                  value === null ? "opacity-100" : "opacity-0"
                )}
              />
              <span className="min-w-0 flex-1 truncate text-sm">{specialOptionLabel}</span>
            </div>
          )}
          {filtered.length === 0 ? (
            <p data-testid="platform-empty" className="py-6 text-center text-sm text-muted-foreground">无符合条件的平台</p>
          ) : (
            filtered.map((p) => {
              const disabled = isOptionDisabled?.(p) ?? false;
              return (
                <div
                  key={p.code}
                  data-testid="platform-option"
                  data-code={p.code}
                  aria-disabled={disabled || undefined}
                  className={cn(
                    "flex items-center gap-2 rounded-sm px-2 py-1.5",
                    disabled
                      ? "cursor-not-allowed opacity-50"
                      : "cursor-pointer hover:bg-muted"
                  )}
                  onClick={disabled ? undefined : () => pick(p.code)}
                >
                  <Check
                    className={cn(
                      "h-4 w-4 shrink-0",
                      p.code === value ? "opacity-100" : "opacity-0"
                    )}
                  />
                  <span className="min-w-0 flex-1 truncate text-sm">
                    {p.name} ({p.code})
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
