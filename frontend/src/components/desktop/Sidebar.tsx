"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import { useUIStore } from "@/stores/uiStore";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  LayoutDashboard,
  Users,
  Briefcase,
  Package,
  Building2,
  Settings,
  FileText,
  PlayCircle,
  ChevronLeft,
  ChevronRight,
  Landmark,
} from "lucide-react";

const adminNavItems = [
  { href: "/dashboard", label: "首页", icon: LayoutDashboard },
  { href: "/investors", label: "投资人", icon: Users },
  { href: "/portfolios", label: "组合", icon: Briefcase },
  { href: "/products", label: "产品", icon: Package },
  { href: "/platforms", label: "平台", icon: Building2 },
  { href: "/logs", label: "日志", icon: FileText },
  { href: "/tasks", label: "任务", icon: PlayCircle },
  { href: "/settings", label: "设置", icon: Settings },
];

const viewerNavItems = [
  { href: "/dashboard", label: "首页", icon: LayoutDashboard },
  { href: "/portfolios", label: "组合", icon: Briefcase },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuthStore();
  const { sidebarCollapsed, toggleSidebarCollapse } = useUIStore();

  const navItems = user?.role === "admin" ? adminNavItems : viewerNavItems;

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          "hidden lg:flex flex-col border-r bg-background h-[calc(100vh-4rem)] sticky top-16 transition-all duration-300",
          sidebarCollapsed ? "w-16" : "w-64"
        )}
      >
        {/* Logo / Brand */}
        <div className="flex items-center justify-between h-14 px-4 border-b">
          {!sidebarCollapsed && (
            <Link href="/dashboard" className="flex items-center gap-2 font-bold text-lg">
              <Landmark className="h-5 w-5 text-primary" />
              <span>InvestRing</span>
            </Link>
          )}
          {sidebarCollapsed && (
            <Landmark className="h-5 w-5 text-primary mx-auto" />
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              pathname === item.href || pathname.startsWith(`${item.href}/`);

            if (sidebarCollapsed) {
              return (
                <Tooltip key={item.href}>
                  <TooltipTrigger asChild>
                    <Link
                      href={item.href}
                      className={cn(
                        "flex items-center justify-center h-10 w-10 mx-auto rounded-lg transition-colors",
                        isActive
                          ? "bg-primary text-primary-foreground"
                          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                      )}
                    >
                      <Icon className="h-5 w-5" />
                    </Link>
                  </TooltipTrigger>
                  <TooltipContent side="right">{item.label}</TooltipContent>
                </Tooltip>
              );
            }

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )}
              >
                <Icon className="h-5 w-5 shrink-0" />
                <span className="truncate">{item.label}</span>
                {isActive && (
                  <span className="ml-auto h-1.5 w-1.5 rounded-full bg-primary-foreground" />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Collapse Toggle */}
        <div className="border-t p-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleSidebarCollapse}
            className={cn(
              "w-full flex items-center gap-2 text-muted-foreground hover:text-foreground",
              sidebarCollapsed && "justify-center px-0"
            )}
          >
            {sidebarCollapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <>
                <ChevronLeft className="h-4 w-4" />
                <span className="text-xs">收起侧边栏</span>
              </>
            )}
          </Button>
        </div>
      </aside>
    </TooltipProvider>
  );
}
