"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { shareChangeEventApi, getErrorMessage, ApiException } from "@/lib/api";
import { ShareChangeEventCreate } from "@/types/share-change-event";
import { queryKeys } from "@/lib/queryKeys";
import { useUIStore } from "@/stores/uiStore";

// 份额变动事件列表 Hook
export function useShareChangeEventList(portfolioCode: string, params?: { page?: number; page_size?: number }) {
  return useQuery({
    queryKey: queryKeys.shareChangeEvents.list(portfolioCode),
    queryFn: () => shareChangeEventApi.list({ portfolio_code: portfolioCode, page_size: 100, ...params }),
    enabled: !!portfolioCode,
    staleTime: 30 * 1000,
  });
}

// 创建份额变动事件 Hook（支持 force_cover 强制提交）
export function useCreateShareChangeEvent(portfolioCode: string) {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: ({ data, forceCover }: { data: ShareChangeEventCreate; forceCover?: boolean }) =>
      shareChangeEventApi.create(data, { forceCover }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.shareChangeEvents.list(portfolioCode) });
      addToast({
        type: "success",
        title: "创建成功",
        message: "份额变动事件已创建",
      });
    },
    onError: (error: unknown) => {
      // PLATFORM_NOT_COVERED：调用方会弹确认框引导 force_cover 重试，此处不叠加 toast
      if (error instanceof ApiException && error.code === "PLATFORM_NOT_COVERED") {
        return;
      }
      addToast({
        type: "error",
        title: "创建失败",
        message: getErrorMessage(error, "请检查输入数据后重试"),
      });
    },
  });
}

// 确认份额变动事件 Hook
export function useConfirmShareChangeEvent(portfolioCode: string) {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (id: number) => shareChangeEventApi.confirm(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.shareChangeEvents.list(portfolioCode) });
      addToast({
        type: "success",
        title: "确认成功",
        message: "份额变动事件已确认",
      });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "确认失败",
        message: getErrorMessage(error, "请稍后重试"),
      });
    },
  });
}

// 取消份额变动事件 Hook
export function useCancelShareChangeEvent(portfolioCode: string) {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (id: number) => shareChangeEventApi.cancel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.shareChangeEvents.list(portfolioCode) });
      addToast({
        type: "success",
        title: "取消成功",
        message: "份额变动事件已取消",
      });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "取消失败",
        message: getErrorMessage(error, "请稍后重试"),
      });
    },
  });
}
