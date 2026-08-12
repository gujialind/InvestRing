"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Briefcase, TrendingUp, Users, Wallet } from "lucide-react";
import { formatCurrency, formatReturnRate, getReturnColorClass } from "@/lib/utils";

interface DashboardStatsCardsProps {
  totalValue: number;
  avgReturn: number;
  activeCount: number;
  totalCount: number;
  investorCount: number;
  variant?: "desktop" | "mobile";
}

interface StatItem {
  icon: typeof Wallet;
  iconCls: string;
  label: string;
  value: string;
  valueCls: string;
  sub: string;
}

/**
 * 首页 4 项统计卡片（总资产/平均收益/活跃组合/投资人）。
 * 桌面端与移动端共用同一数据，仅布局通过 variant 区分。
 */
export default function DashboardStatsCards({
  totalValue,
  avgReturn,
  activeCount,
  totalCount,
  investorCount,
  variant = "desktop",
}: DashboardStatsCardsProps) {
  const items: StatItem[] = [
    {
      icon: Wallet,
      iconCls: "text-muted-foreground",
      label: variant === "mobile" ? "总资产" : "总资产",
      value: formatCurrency(totalValue),
      valueCls: "",
      sub: variant === "mobile" ? `${activeCount} 个活跃组合` : `${activeCount} 个活跃组合合计`,
    },
    {
      icon: TrendingUp,
      iconCls: getReturnColorClass(avgReturn),
      label: variant === "mobile" ? "平均收益" : "平均累计收益",
      value: formatReturnRate(avgReturn),
      valueCls: getReturnColorClass(avgReturn),
      sub: variant === "mobile" ? "活跃组合平均" : "活跃组合平均值",
    },
    {
      icon: Briefcase,
      iconCls: "text-muted-foreground",
      label: "活跃组合",
      value: String(activeCount),
      valueCls: "",
      sub: `共 ${totalCount} 个组合`,
    },
    {
      icon: Users,
      iconCls: "text-muted-foreground",
      label: "投资人",
      value: String(investorCount),
      valueCls: "",
      sub: variant === "mobile" ? "系统注册" : "系统注册投资人",
    },
  ];

  if (variant === "mobile") {
    return (
      <div className="grid grid-cols-2 gap-3">
        {items.map((item) => (
          <Card key={item.label}>
            <CardContent className="p-3">
              <div className="flex items-center gap-2 mb-1">
                <item.icon className={`h-4 w-4 ${item.iconCls}`} />
                <span className="text-xs text-muted-foreground">{item.label}</span>
              </div>
              <div className={`text-lg font-bold ${item.valueCls}`}>{item.value}</div>
              <p className="text-xs text-muted-foreground mt-1">{item.sub}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {items.map((item) => (
        <Card key={item.label}>
          <CardContent className="pt-6">
            <div className="flex flex-row items-center justify-between pb-2">
              <span className="text-sm font-medium">{item.label}</span>
              <item.icon className={`h-4 w-4 ${item.iconCls}`} />
            </div>
            <div className={`text-2xl font-bold ${item.valueCls}`}>{item.value}</div>
            <p className="text-xs text-muted-foreground mt-1">{item.sub}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
