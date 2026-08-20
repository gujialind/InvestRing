"use client"

import * as React from "react"
import * as PopoverPrimitive from "@radix-ui/react-popover"

import { cn } from "@/lib/utils"
import { DialogPortalContainerContext } from "@/components/ui/dialog"

const Popover = PopoverPrimitive.Root

const PopoverTrigger = PopoverPrimitive.Trigger

interface PopoverContentProps
  extends React.ComponentPropsWithoutRef<typeof PopoverPrimitive.Content> {
  /** 显式指定 Portal 容器，优先级高于 Dialog context；缺省自动适配 */
  container?: HTMLElement | null
}

const PopoverContent = React.forwardRef<
  React.ElementRef<typeof PopoverPrimitive.Content>,
  PopoverContentProps
>(({ className, align = "center", sideOffset = 4, container, ...props }, ref) => {
  // issue #191：Popover 位于 Dialog 内时，弹层 Portal 到 DialogContent 节点内，
  // 避免 modal Dialog 的 body pointer-events:none 使弹层点击不可达、
  // 以及弹层被判定为 outside pointerdown 误关 Dialog；弹窗外场景保持 body 默认
  const dialogContainer = React.useContext(DialogPortalContainerContext)
  const portalContainer = container ?? dialogContainer
  const content = (
    <PopoverPrimitive.Content
      ref={ref}
      align={align}
      sideOffset={sideOffset}
      className={cn(
        "z-50 w-auto rounded-md border bg-popover p-3 text-popover-foreground shadow-lg outline-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
        className
      )}
      {...props}
    />
  )
  return portalContainer ? (
    <PopoverPrimitive.Portal container={portalContainer}>
      {content}
    </PopoverPrimitive.Portal>
  ) : (
    <PopoverPrimitive.Portal>{content}</PopoverPrimitive.Portal>
  )
})
PopoverContent.displayName = PopoverPrimitive.Content.displayName

export { Popover, PopoverTrigger, PopoverContent }
