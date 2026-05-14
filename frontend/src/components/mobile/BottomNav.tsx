"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import { useUIStore } from "@/stores/uiStore";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Users,
  Briefcase,
  Package,
  Settings,
  Landmark,
} from "lucide-react";

const adminNavItems = [
  { href: "/dashboard", label: "首页", icon: LayoutDashboard },
  { href: "/investors", label: "投资人", icon: Users },
  { href: "/portfolio", label: "组合", icon: Briefcase },
  { href: "/products", label: "产品", icon: Package },
  { href: "/settings", label: "设置", icon: Settings },
];

const viewerNavItems = [
  { href: "/dashboard", label: "首页", icon: LayoutDashboard },
  { href: "/portfolio", label: "组合", icon: Briefcase },
];

export default function BottomNav() {
  const pathname = usePathname();
  const { user } = useAuthStore();
  const { mobileNavVisible } = useUIStore();

  const navItems = user?.role === "admin" ? adminNavItems : viewerNavItems;

  if (!mobileNavVisible) {
    return null;
  }

  return (
    <nav className="lg:hidden fixed bottom-0 left-0 right-0 border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 z-50 safe-area-pb">
      <div className="flex justify-around items-center h-16">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive =
            pathname === item.href || pathname.startsWith(`${item.href}/`);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-col items-center justify-center gap-0.5 min-w-[3.5rem] h-full px-2 text-xs font-medium transition-colors",
                isActive
                  ? "text-primary"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <div
                className={cn(
                  "flex items-center justify-center h-8 w-8 rounded-lg transition-colors",
                  isActive && "bg-primary/10"
                )}
              >
                <Icon className="h-5 w-5" />
              </div>
              <span className="scale-90 origin-top">{item.label}</span>
              {isActive && (
                <span className="absolute bottom-1 h-1 w-1 rounded-full bg-primary" />
              )}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
