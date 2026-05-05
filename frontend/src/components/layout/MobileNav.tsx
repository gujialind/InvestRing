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
  Settings,
} from "lucide-react";

const adminNavItems = [
  { href: "/dashboard", label: "首页", icon: LayoutDashboard },
  { href: "/investors", label: "投资人", icon: Users },
  { href: "/portfolios", label: "组合", icon: Briefcase },
  { href: "/products", label: "产品", icon: Package },
  { href: "/settings", label: "设置", icon: Settings },
];

const viewerNavItems = [
  { href: "/dashboard", label: "首页", icon: LayoutDashboard },
  { href: "/portfolios", label: "组合", icon: Briefcase },
];

export default function MobileNav() {
  const pathname = usePathname();
  const { user } = useAuthStore();

  const navItems = user?.role === "admin" ? adminNavItems : viewerNavItems;

  return (
    <nav className="lg:hidden fixed bottom-0 left-0 right-0 border-t bg-background z-50">
      <div className="flex justify-around items-center h-16">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-col items-center gap-1 px-3 py-2 text-xs font-medium transition-colors",
                isActive
                  ? "text-primary"
                  : "text-muted-foreground"
              )}
            >
              <Icon className="h-5 w-5" />
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
