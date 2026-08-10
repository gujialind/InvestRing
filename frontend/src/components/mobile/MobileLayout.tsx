"use client";

import { usePathname } from "next/navigation";
import BottomNav from "./BottomNav";
import { cn } from "@/lib/utils";

// 一级 Tab 页（BottomNav 导航项对应页面，精确匹配）
// viewer 的导航项是其子集，无需按角色区分——BottomNav 内部已按角色出项
const TOP_LEVEL_PATHS = new Set([
  "/m/dashboard",
  "/m/investors",
  "/m/portfolio",
  "/m/products",
  "/m/settings",
]);

export default function MobileLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  // 仅一级 Tab 页显示底部导航；钻取页（/m/portfolio/P001）、/m/platforms 等隐藏
  const showNav = TOP_LEVEL_PATHS.has(pathname);

  return (
    <div className={cn("min-h-screen bg-background", showNav && "pb-16")}>
      <main className="p-4">{children}</main>
      {showNav && <BottomNav />}
    </div>
  );
}
