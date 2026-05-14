"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { formatReturnRate } from "@/lib/utils";

interface ReturnPoint {
  period: string;
  value: number;
}

interface ReturnChartProps {
  data: ReturnPoint[];
  height?: number;
}

export default function ReturnChart({ data, height = 250 }: ReturnChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center text-muted-foreground" style={{ height }}>
        暂无收益数据
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis dataKey="period" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} tickFormatter={(value) => `${value.toFixed(1)}%`} />
        <Tooltip formatter={(value: number) => [`${formatReturnRate(value)}`, "收益率"]} />
        <Bar dataKey="value" radius={[4, 4, 0, 0]} name="收益率">
          {data.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={entry.value >= 0 ? "#10b981" : "#ef4444"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}