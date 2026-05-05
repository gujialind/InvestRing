"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/stores/auth";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Users,
  Briefcase,
  Package,
  Building2,
  Settings,
  FileText,
  PlayCircle,
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

  const navItems = user?.role === "admin" ? adminNavItems : viewerNavItems;

  return (
    <aside className="hidden lg:block w-64 border-r bg-background">
      <nav className="flex flex-col gap-2 p-4">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
