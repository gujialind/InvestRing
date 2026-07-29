"use client";

import { useQuery } from "@tanstack/react-query";
import { systemApi } from "@/lib/api";

// 交易日历 Hook：按年缓存（日历数据基本不变，长 staleTime 避免重复请求）
export function useTradingCalendar(year: number, enabled = true) {
  return useQuery({
    queryKey: ["trading-calendar", year],
    queryFn: () => systemApi.getTradingCalendar(year),
    enabled: enabled && year > 0,
    staleTime: 24 * 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
  });
}
