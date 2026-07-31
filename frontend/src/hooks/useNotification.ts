"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { notificationApi, getErrorMessage } from "@/lib/api";
import { useUIStore } from "@/stores/uiStore";

const NOTIFICATION_QUERY_KEY = "notifications";

// 通知列表 Hook（60s 轮询，供铃铛角标与下拉列表使用）
export function useNotificationList(params?: { page?: number; page_size?: number; status?: string }) {
  return useQuery({
    queryKey: [NOTIFICATION_QUERY_KEY, "list", params],
    queryFn: () => notificationApi.list(params),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}

// 标记单条已读 Hook
export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (id: number) => notificationApi.markAsRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [NOTIFICATION_QUERY_KEY] });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "操作失败",
        message: getErrorMessage(error, "请稍后重试"),
      });
    },
  });
}

// 全部已读 Hook
export function useMarkAllNotificationsRead() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: () => notificationApi.markAllAsRead(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [NOTIFICATION_QUERY_KEY] });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "操作失败",
        message: getErrorMessage(error, "请稍后重试"),
      });
    },
  });
}
