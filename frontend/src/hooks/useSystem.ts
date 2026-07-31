"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { systemApi, getErrorMessage } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import { useUIStore } from "@/stores/uiStore";

// 数据源配置 Hook
export function useDataSourceConfig() {
  return useQuery({
    queryKey: queryKeys.dataSources.config(),
    queryFn: () => systemApi.getDataSourceConfig(),
    staleTime: 30 * 1000,
  });
}

// 更新数据源配置 Hook（tushare: api_key / akshare: is_enabled）
export function useUpdateDataSource() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: ({ name, data }: {
      name: "tushare" | "akshare";
      data: { api_key?: string; is_enabled?: boolean };
    }) => systemApi.updateDataSource(name, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.dataSources.config() });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "保存失败",
        message: getErrorMessage(error, "请稍后重试"),
      });
    },
  });
}

// 同步交易日历 Hook
export function useSyncTradingCalendar() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (year: number) => systemApi.syncTradingCalendar(year),
    onSuccess: (data, year) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tradingCalendar.byYear(year) });
      addToast({
        type: "success",
        title: "同步成功",
        message: `已新增 ${data.synced_count} 条交易日历记录`,
      });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "同步失败",
        message: getErrorMessage(error, "请检查 Tushare Token 配置"),
      });
    },
  });
}
