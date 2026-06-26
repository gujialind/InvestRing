"use client"

import * as React from "react"
import { format } from "date-fns"
import { CalendarIcon, X } from "lucide-react"
import { zhCN } from "date-fns/locale"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"

interface DatePickerProps {
  date?: Date
  onSelect?: (date: Date | undefined) => void
  placeholder?: string
  className?: string
  disabled?: boolean
}

export function DatePicker({
  date,
  onSelect,
  placeholder = "选择日期",
  className,
  disabled = false,
}: DatePickerProps) {
  const [open, setOpen] = React.useState(false)

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <div className="relative">
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            disabled={disabled}
            className={cn(
              "w-full justify-start text-left font-normal pr-9",
              !date && "text-muted-foreground",
              className
            )}
          >
            <CalendarIcon className="mr-2 h-4 w-4 shrink-0" />
            {date ? format(date, "yyyy-MM-dd") : placeholder}
          </Button>
        </PopoverTrigger>
        {date && !disabled ? (
          <button
            type="button"
            aria-label="清除日期"
            onClick={(e) => {
              e.stopPropagation()
              onSelect?.(undefined)
            }}
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
        <Calendar
          mode="single"
          selected={date}
          onSelect={(newDate) => {
            onSelect?.(newDate)
            if (newDate) {
              setOpen(false)
            }
          }}
          autoFocus
          locale={zhCN}
        />
      </PopoverContent>
    </Popover>
  )
}
