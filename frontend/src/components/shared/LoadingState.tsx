"use client";

import { Loader2 } from "lucide-react";

/**
 * 全屏居中加载状态。
 * 由各页面在数据加载中时渲染（不包含 Layout，需外层包裹）。
 */
export default function LoadingState({ height = "60vh" }: { height?: string }) {
  return (
    <div className="flex items-center justify-center" style={{ height }}>
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
    </div>
  );
}
