"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { platformApi, getErrorMessage, PlatformCreate, PlatformUpdate } from "@/lib/api";
import { useUIStore } from "@/stores/uiStore";

const PLATFORM_QUERY_KEY = "platforms";

// 平台列表 Hook
export function usePlatformList(params?: { page?: number; page_size?: number }) {
  return useQuery({
    queryKey: [PLATFORM_QUERY_KEY, "list", params],
    queryFn: () => platformApi.list(params),
    staleTime: 60 * 1000,
  });
}

// 单个平台详情 Hook
export function usePlatform(code: string) {
  return useQuery({
    queryKey: [PLATFORM_QUERY_KEY, code],
    queryFn: () => platformApi.get(code),
    enabled: !!code,
    staleTime: 60 * 1000,
  });
}

// 创建平台 Hook
export function useCreatePlatform() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (data: PlatformCreate) => platformApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PLATFORM_QUERY_KEY] });
      addToast({ type: "success", title: "创建成功", message: "平台已创建" });
    },
    onError: (error: unknown) => {
      addToast({ type: "error", title: "创建失败", message: getErrorMessage(error, "请检查输入信息") });
    },
  });
}

// 更新平台 Hook（code 随 mutate 传入）
export function useUpdatePlatform() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: ({ code, data }: { code: string; data: PlatformUpdate }) =>
      platformApi.update(code, data),
    onSuccess: (_, { code }) => {
      queryClient.invalidateQueries({ queryKey: [PLATFORM_QUERY_KEY, code] });
      queryClient.invalidateQueries({ queryKey: [PLATFORM_QUERY_KEY, "list"] });
      addToast({ type: "success", title: "更新成功", message: "平台信息已更新" });
    },
    onError: (error: unknown) => {
      addToast({ type: "error", title: "更新失败", message: getErrorMessage(error, "请稍后重试") });
    },
  });
}

// 删除平台 Hook
export function useDeletePlatform() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (code: string) => platformApi.delete(code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PLATFORM_QUERY_KEY, "list"] });
      addToast({ type: "success", title: "删除成功", message: "平台已删除" });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "删除失败",
        message: getErrorMessage(error, "该平台已被使用，无法删除"),
      });
    },
  });
}
