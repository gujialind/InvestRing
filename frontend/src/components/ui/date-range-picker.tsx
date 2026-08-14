"use client"

import * as React from "react"
import {
  differenceInCalendarDays,
  endOfYear,
  format,
  isSameDay,
  startOfMonth,
  startOfQuarter,
  startOfYear,
  subDays,
  subMonths,
  subYears,
} from "date-fns"
import type { DateRange } from "react-day-picker"
import { CalendarIcon, X } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"

// 快捷选项（规范 §10：形态统一，清单由业务定义；区间语义在此定死）
const QUICK_OPTIONS: { key: string; label: string; range: (now: Date) => DateRange }[] = [
  { key: "this-month", label: "本月", range: (now) => ({ from: startOfMonth(now), to: now }) },
  { key: "this-quarter", label: "本季度", range: (now) => ({ from: startOfQuarter(now), to: now }) },
  { key: "this-year", label: "今年", range: (now) => ({ from: startOfYear(now), to: now }) },
  { key: "last-year", label: "去年", range: (now) => ({ from: startOfYear(subYears(now, 1)), to: endOfYear(subYears(now, 1)) }) },
  { key: "last-7d", label: "最近7天", range: (now) => ({ from: subDays(now, 6), to: now }) },
  { key: "last-1m", label: "最近1个月", range: (now) => ({ from: subMonths(now, 1), to: now }) },
  { key: "last-1y", label: "最近1年", range: (now) => ({ from: subYears(now, 1), to: now }) },
  { key: "last-3y", label: "最近3年", range: (now) => ({ from: subYears(now, 3), to: now }) },
]

// 手选区间与某快捷项完全一致（isSameDay 双端比较）→ 返回其 key，否则 null
function matchQuickOption(value: DateRange | undefined): string | null {
  if (!value?.from || !value.to) return null
  const now = new Date()
  for (const opt of QUICK_OPTIONS) {
    const r = opt.range(now)
    if (r.from && r.to && isSameDay(value.from, r.from) && isSameDay(value.to, r.to)) {
      return opt.key
    }
  }
  return null
}

interface DateRangePickerProps {
  value?: DateRange
  onChange?: (range: DateRange | undefined) => void
  placeholder?: string
  className?: string
  disabled?: boolean
  /** 调用方按端传：桌面 2 / 移动 1（规范 §10）；快捷项布局随之一左置/置顶 */
  numberOfMonths?: 1 | 2
}

export function DateRangePicker({
  value,
  onChange,
  placeholder = "选择日期区间",
  className,
  disabled = false,
  numberOfMonths = 2,
}: DateRangePickerProps) {
  const [open, setOpen] = React.useState(false)
  // 草稿态（#154，规范 §10）：弹层内手选/快捷项只填草稿，「确定」才提交 onChange；
  // 规避 react-day-picker v10 addToRange「空区间首击即得完整单日区间」导致的误关闭
  const [draft, setDraft] = React.useState<DateRange | undefined>(value)
  // 快捷项选中态：随草稿/外部值按 isSameDay 联动（一致保持/否则解除）
  const [quickKey, setQuickKey] = React.useState<string | null>(() => matchQuickOption(value))

  // 外部重置 value（如筛选栏「重置」恢复默认区间）时同步快捷项选中态
  React.useEffect(() => {
    setQuickKey(matchQuickOption(value))
  }, [value])

  const handleOpenChange = (next: boolean) => {
    if (next) {
      // 打开时以当前提交值为草稿起点；关闭未确定则草稿自然丢弃
      setDraft(value)
      setQuickKey(matchQuickOption(value))
    }
    setOpen(next)
  }

  const handleSelect = (range: DateRange | undefined) => {
    // v10 语义：空草稿首击即得 {D,D} 单日区间；完整单日区间再点同一日返回 undefined（清空草稿）
    setDraft(range)
    setQuickKey(matchQuickOption(range))
  }

  const handleQuick = (opt: (typeof QUICK_OPTIONS)[number]) => {
    const range = opt.range(new Date())
    setDraft(range)
    setQuickKey(opt.key)
  }

  const handleConfirm = () => {
    if (!draft?.from) return
    onChange?.(draft)
    setOpen(false)
  }

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation()
    setQuickKey(null)
    onChange?.(undefined)
  }

  const label = value?.from
    ? `${format(value.from, "yyyy-MM-dd")} ~ ${value.to ? format(value.to, "yyyy-MM-dd") : ""}`
    : placeholder

  const draftSummary = draft?.from
    ? `${format(draft.from, "yyyy-MM-dd")} ~ ${draft.to ? format(draft.to, "yyyy-MM-dd") : ""} · 共 ${differenceInCalendarDays(draft.to ?? draft.from, draft.from) + 1} 天`
    : "请点选起止日期"

  const quickPanel = (
    <div
      className={cn(
        "flex gap-1 p-3",
        numberOfMonths === 2
          ? "flex-col border-r pr-2"
          : "flex-row flex-wrap border-b pb-2"
      )}
    >
      {QUICK_OPTIONS.map((opt) => (
        <button
          key={opt.key}
          type="button"
          onClick={() => handleQuick(opt)}
          className={cn(
            "shrink-0 whitespace-nowrap rounded-md px-2 py-1 text-left text-xs transition-colors hover:bg-muted",
            quickKey === opt.key && "bg-success-soft font-medium text-success-foreground hover:bg-success-soft"
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <div className="relative">
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            disabled={disabled}
            title={label}
            className={cn(
              "w-full justify-start whitespace-nowrap pr-9 text-left font-normal transition-colors hover:border-primary/40",
              !value?.from && "text-muted-foreground",
              className
            )}
          >
            <CalendarIcon className="mr-2 h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="truncate">{label}</span>
          </Button>
        </PopoverTrigger>
        {value?.from && !disabled ? (
          <button
            type="button"
            aria-label="清除日期区间"
            onClick={handleClear}
            className="absolute right-2 top-1/2 flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        ) : null}
      </div>
      <PopoverContent
        align="start"
        className="w-auto p-0"
        onCloseAutoFocus={(e) => e.preventDefault()}
      >
        <div className="flex flex-col">
          <div className={cn("flex", numberOfMonths === 2 ? "flex-row" : "flex-col")}>
            {quickPanel}
            <Calendar
              mode="range"
              selected={draft}
              onSelect={handleSelect}
              defaultMonth={draft?.to ?? draft?.from}
              numberOfMonths={numberOfMonths}
              autoFocus
            />
          </div>
          <div className="flex items-center justify-between gap-2 border-t px-3 py-2">
            <span className="text-xs text-muted-foreground">{draftSummary}</span>
            <Button type="button" size="sm" onClick={handleConfirm} disabled={!draft?.from}>
              确定
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}
