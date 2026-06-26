"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LucideIcon } from "lucide-react";
import { ReactNode } from "react";

interface StatCardProps {
  title: string;
  value: ReactNode;
  icon: LucideIcon;
  iconClassName?: string;
  valueClassName?: string;
  description?: string;
}

/**
 * 桌面端统计卡片：标题在左、图标在右，2xl 数值。
 */
export default function StatCard({
  title,
  value,
  icon: Icon,
  iconClassName = "text-muted-foreground",
  valueClassName,
  description,
}: StatCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className={`h-4 w-4 ${iconClassName}`} />
      </CardHeader>
      <CardContent>
        <div className={`text-2xl font-bold ${valueClassName || ""}`}>{value}</div>
        {description && <p className="text-xs text-muted-foreground mt-1">{description}</p>}
      </CardContent>
    </Card>
  );
}
