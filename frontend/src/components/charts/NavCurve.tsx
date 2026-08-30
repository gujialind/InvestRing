"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { CHART_OTHER, NAV_LINE } from "@/lib/colors";
import { formatNav } from "@/lib/utils";

interface NavPoint {
  date: string;
  nav: number;
}

interface NavCurveProps {
  data: NavPoint[];
  height?: number;
  initialNav?: number;
}

export default function NavCurve({ data, height = 300, initialNav = 1.0 }: NavCurveProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center text-muted-foreground" style={{ height }}>
        暂无净值数据
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 12 }}
          tickFormatter={(value) => value.slice(5)}
        />
        <YAxis
          domain={["auto", "auto"]}
          tick={{ fontSize: 12 }}
          tickFormatter={(value) => formatNav(value)}
        />
        <Tooltip
          formatter={(value) => [formatNav(Number(value)), "净值"]}
          labelFormatter={(label) => `日期: ${label}`}
        />
        <ReferenceLine
          y={initialNav}
          stroke={CHART_OTHER}
          strokeDasharray="5 5"
          label={{ value: "初始净值", position: "right", fontSize: 12 }}
        />
        <Line
          type="monotone"
          dataKey="nav"
          stroke={NAV_LINE}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4 }}
          name="组合净值"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}