"use client"

import * as React from "react"
import {
  DayPicker,
  getDefaultClassNames,
  type ChevronProps,
  type DayButtonProps,
  type DropdownProps,
} from "react-day-picker"
import { zhCN } from "date-fns/locale"
import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react"

import { cn } from "@/lib/utils"
import { buttonVariants } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select"

export type CalendarProps = React.ComponentProps<typeof DayPicker>

// react-day-picker 默认用原生 <select> 渲染年/月下拉框，放在 Radix Popover 中时，
// 点击原生下拉项会被 Popover 的 DismissableLayer 判定为"外部交互"而关闭弹层。
// 改用 Radix Select 替换原生 <select>：二者同属 Radix 体系，下拉内容以嵌套层级注册，
// 点击选项不再触发外层 Popover 关闭（与 shadcn combobox 同理）。
function CalendarDropdown({
  options,
  value,
  onChange,
  disabled,
  className,
  style,
  "aria-label": ariaLabel,
}: DropdownProps) {
  const selected = options?.find((option) => String(option.value) === String(value))

  return (
    <Select
      value={value != null ? String(value) : undefined}
      onValueChange={(next) => {
        // react-day-picker 内部读取 e.target.value 后执行 Number(...)，这里合成事件
        onChange?.({
          target: { value: next },
        } as React.ChangeEvent<HTMLSelectElement>)
      }}
      disabled={disabled}
    >
      <SelectTrigger
        className={cn(
          "inline-flex h-8 w-auto min-w-[4.5rem] items-center gap-1 rounded-md border border-input bg-background px-2 py-1 text-sm font-medium",
          className
        )}
        style={style}
        aria-label={ariaLabel}
        disabled={disabled}
      >
        <span className="truncate">{selected?.label ?? ariaLabel}</span>
      </SelectTrigger>
      <SelectContent position="popper">
        {options?.map((option) => (
          <SelectItem
            key={option.value}
            value={String(option.value)}
            disabled={option.disabled}
          >
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

// 用 lucide 图标替换默认 SVG，导航箭头与设计系统一致
function CalendarChevron({ orientation = "left", className, style }: ChevronProps) {
  const iconClass = cn("size-4", className)
  if (orientation === "left") {
    return <ChevronLeft className={iconClass} style={style} />
  }
  if (orientation === "right") {
    return <ChevronRight className={iconClass} style={style} />
  }
  return <ChevronDown className={iconClass} style={style} />
}

// v10 的 aria-selected/data-* 在 <td> 上，按钮只拿 rdp-day_button。
// 自定义 DayButton 读 modifiers 并在按钮自身设置 data-*，再用 data-[...]: 控制选中态。
function CalendarDayButton({
  className,
  day,
  modifiers,
  ...props
}: DayButtonProps) {
  const ref = React.useRef<HTMLButtonElement>(null)
  React.useEffect(() => {
    if (modifiers.focused) ref.current?.focus()
  }, [modifiers.focused])

  return (
    <button
      ref={ref}
      type="button"
      data-day={day.isoDate}
      data-selected-single={
        modifiers.selected &&
        !modifiers.range_start &&
        !modifiers.range_end &&
        !modifiers.range_middle
      }
      data-range-start={modifiers.range_start}
      data-range-end={modifiers.range_end}
      data-range-middle={modifiers.range_middle}
      className={cn(
        buttonVariants({ variant: "ghost" }),
        "size-9 p-0 font-normal",
        "data-[selected-single=true]:bg-primary data-[selected-single=true]:text-primary-foreground data-[selected-single=true]:hover:bg-primary",
        "data-[range-start=true]:bg-primary data-[range-start=true]:text-primary-foreground data-[range-start=true]:rounded-l-md",
        "data-[range-end=true]:bg-primary data-[range-end=true]:text-primary-foreground data-[range-end=true]:rounded-r-md",
        "data-[range-middle=true]:bg-success-soft data-[range-middle=true]:text-success-foreground data-[range-middle=true]:rounded-none",
        "group-data-[focused=true]/day:z-10 group-data-[focused=true]/day:ring-2 group-data-[focused=true]/day:ring-ring group-data-[focused=true]/day:ring-offset-2",
        className
      )}
      {...props}
    />
  )
}

function Calendar({
  className,
  classNames,
  components,
  formatters,
  showOutsideDays = true,
  locale = zhCN,
  captionLayout = "dropdown",
  ...props
}: CalendarProps) {
  const defaultClassNames = getDefaultClassNames()

  return (
    <DayPicker
      showOutsideDays={showOutsideDays}
      locale={locale}
      captionLayout={captionLayout}
      formatters={formatters}
      className={cn("bg-background p-3 text-sm", className)}
      components={{
        Chevron: CalendarChevron,
        Dropdown: CalendarDropdown,
        DayButton: CalendarDayButton,
        ...components,
      }}
      classNames={{
        root: cn("w-fit", defaultClassNames.root),
        months: cn("relative flex flex-col gap-4", defaultClassNames.months),
        month: cn("flex w-full flex-col gap-4", defaultClassNames.month),
        nav: cn(
          "pointer-events-none absolute inset-x-0 top-0 z-10 flex h-9 items-center justify-between px-1",
          defaultClassNames.nav
        ),
        button_previous: cn(
          buttonVariants({ variant: "ghost" }),
          "pointer-events-auto size-9 p-0 aria-disabled:opacity-50",
          defaultClassNames.button_previous
        ),
        button_next: cn(
          buttonVariants({ variant: "ghost" }),
          "pointer-events-auto size-9 p-0 aria-disabled:opacity-50",
          defaultClassNames.button_next
        ),
        month_caption: cn(
          "flex h-9 w-full items-center justify-center",
          defaultClassNames.month_caption
        ),
        dropdowns: cn(
          "flex h-9 items-center justify-center gap-1.5 text-sm font-medium",
          defaultClassNames.dropdowns
        ),
        caption_label: cn(
          "text-sm font-medium select-none",
          defaultClassNames.caption_label
        ),
        month_grid: cn("border-collapse", defaultClassNames.month_grid),
        weekdays: defaultClassNames.weekdays,
        weekday: cn(
          "w-9 py-1 text-center text-xs font-normal text-muted-foreground select-none",
          defaultClassNames.weekday
        ),
        week: defaultClassNames.week,
        week_number: cn(
          "w-9 text-xs text-muted-foreground select-none",
          defaultClassNames.week_number
        ),
        week_number_header: cn(
          "w-9 select-none",
          defaultClassNames.week_number_header
        ),
        day: cn(
          "group/day relative h-9 w-9 p-0 text-center select-none",
          defaultClassNames.day
        ),
        selected: defaultClassNames.selected,
        today: cn(
          "rounded-md bg-accent text-accent-foreground",
          defaultClassNames.today
        ),
        outside: cn("text-muted-foreground", defaultClassNames.outside),
        disabled: cn(
          "text-muted-foreground opacity-50",
          defaultClassNames.disabled
        ),
        hidden: cn("invisible", defaultClassNames.hidden),
        range_start: cn("rounded-l-md bg-accent", defaultClassNames.range_start),
        range_middle: cn("rounded-none bg-success-soft text-success-foreground", defaultClassNames.range_middle),
        range_end: cn("rounded-r-md bg-accent", defaultClassNames.range_end),
        ...classNames,
      }}
      {...props}
    />
  )
}
Calendar.displayName = "Calendar"

export { Calendar }
