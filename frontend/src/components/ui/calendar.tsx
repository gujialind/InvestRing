"use client"

import * as React from "react"
import { DayPicker } from "react-day-picker"
import { zhCN } from "date-fns/locale"

import { cn } from "@/lib/utils"

export type CalendarProps = React.ComponentProps<typeof DayPicker>

function Calendar({
  className,
  showOutsideDays = true,
  locale = zhCN,
  captionLayout = "dropdown",
  ...props
}: CalendarProps) {
  return (
    <DayPicker
      showOutsideDays={showOutsideDays}
      locale={locale}
      captionLayout={captionLayout}
      className={cn("p-3", className)}
      classNames={{
        months: "flex flex-col sm:flex-row space-y-4 sm:space-x-4 sm:space-y-0",
        month: "space-y-4",
        caption_label: "text-sm font-medium hidden", // 隐藏默认标签，只显示下拉框
        day_button: cn(
          "h-9 w-9 p-0 font-normal rounded-md",
          "hover:bg-accent hover:text-accent-foreground transition-colors",
          "aria-selected:opacity-100 aria-selected:bg-primary aria-selected:text-primary-foreground aria-selected:hover:bg-primary aria-selected:hover:text-primary-foreground",
          "focus:bg-ring focus:text-ring-foreground focus:outline-none focus:ring-2 focus:ring-offset-2"
        ),
        range_end: "day-range-end",
        selected: "",
        today: "bg-secondary text-secondary-foreground font-semibold",
        outside:
          "text-muted-foreground opacity-50 aria-selected:bg-accent/50 aria-selected:text-muted-foreground aria-selected:opacity-30",
        disabled: "text-muted-foreground opacity-50 cursor-not-allowed",
        range_middle:
          "aria-selected:bg-accent aria-selected:text-accent-foreground",
        hidden: "invisible",
        ...props.classNames,
      }}
      {...props}
    />
  )
}
Calendar.displayName = "Calendar"

export { Calendar }
