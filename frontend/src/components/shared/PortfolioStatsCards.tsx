"use client";

import { Card, CardContent } from "@/components/ui/card";
import { TrendingUp, Users, Wallet } from "lucide-react";
import { formatCurrency, formatNumber, formatReturnRate, getReturnColorClass } from "@/lib/utils";

interface PortfolioStatsCardsProps {
  totalValue: number;
  unitPrice: number;
  totalShares: number;
  cumulativeReturn: number;
  /** desktop: 标题左/图标右的大卡片；mobile: 2×2 紧凑卡片 */
  variant?: "desktop" | "mobile";
}

/**
 * 组合详情页 4 项统计卡片（总资产/净值/收益率/总份额）。
 * 桌面端与移动端共用同一数据源，仅布局通过 variant 区分。
 */
export default function PortfolioStatsCards({
  totalValue,
  unitPrice,
  totalShares,
  cumulativeReturn,
  variant = "desktop",
}: PortfolioStatsCardsProps) {
  const returnColor = getReturnColorClass(cumulativeReturn);
  const returnText = formatReturnRate(cumulativeReturn);

  if (variant === "mobile") {
    const items = [
      { icon: Wallet, iconCls: "text-muted-foreground", label: "总资产", value: formatCurrency(totalValue), valueCls: "" },
      { icon: TrendingUp, iconCls: "text-muted-foreground", label: "净值", value: formatNumber(unitPrice, 4), valueCls: "" },
      { icon: TrendingUp, iconCls: "text-red-500", label: "累计收益", value: returnText, valueCls: returnColor },
      { icon: Users, iconCls: "text-muted-foreground", label: "总份额", value: formatNumber(totalShares, 2), valueCls: "" },
    ];
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
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  const items = [
    { title: "总资产", value: formatCurrency(totalValue), icon: Wallet, iconCls: "text-muted-foreground", valueCls: "" },
    { title: "净值", value: formatNumber(unitPrice, 4), icon: TrendingUp, iconCls: "text-muted-foreground", valueCls: "" },
    { title: "收益率", value: returnText, icon: TrendingUp, iconCls: "text-red-500", valueCls: returnColor },
    { title: "总份额", value: formatNumber(totalShares, 2), icon: Users, iconCls: "text-muted-foreground", valueCls: "" },
  ];
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {items.map((item) => (
        <Card key={item.title}>
          <CardContent className="pt-6">
            <div className="flex flex-row items-center justify-between pb-2">
              <span className="text-sm font-medium">{item.title}</span>
              <item.icon className={`h-4 w-4 ${item.iconCls}`} />
            </div>
            <div className={`text-2xl font-bold ${item.valueCls}`}>{item.value}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
