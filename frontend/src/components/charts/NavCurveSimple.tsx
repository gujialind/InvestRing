"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface NavPoint {
  date: string;
  nav: number;
}

interface NavCurveSimpleProps {
  data: NavPoint[];
  height?: number;
}

export default function NavCurveSimple({ data, height = 200 }: NavCurveSimpleProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center text-muted-foreground" style={{ height }}>
        暂无净值数据
      </div>
    );
  }

  const minNav = Math.min(...data.map((d) => d.nav));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
        <defs>
          <linearGradient id="navGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted/30" />
        <XAxis dataKey="date" tick={false} axisLine={false} />
        <YAxis
          domain={[minNav * 0.98, "auto"]}
          tick={{ fontSize: 10 }}
          tickFormatter={(value) => value.toFixed(2)}
          width={40}
        />
        <Tooltip
          formatter={(value: number) => [value.toFixed(4), "净值"]}
          labelFormatter={(label) => `日期: ${label}`}
        />
        <Area
          type="monotone"
          dataKey="nav"
          stroke="#3b82f6"
          strokeWidth={2}
          fill="url(#navGradient)"
          name="组合净值"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}