"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { taskApi, getErrorMessage } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import { useUIStore } from "@/stores/uiStore";

// 定时任务列表 Hook（后端返回分页对象）
export function useTaskList(params?: { page?: number; page_size?: number }) {
  return useQuery({
    queryKey: queryKeys.tasks.list(),
    queryFn: () => taskApi.list(params),
    staleTime: 10 * 1000,
  });
}

// 全局执行历史 Hook
export function useTaskExecutions(params?: {
  task_code?: string;
  page?: number;
  page_size?: number;
}) {
  return useQuery({
    queryKey: queryKeys.tasks.executions(params),
    queryFn: () => taskApi.executionHistory(params),
    staleTime: 10 * 1000,
  });
}

// 手动执行任务 Hook
export function useRunTask() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (code: string) => taskApi.run(code),
    onSuccess: (_, code) => {
      // 任务执行会更新 last_run_at 并写入执行日志，两处均需刷新
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.root });
      addToast({ type: "success", title: "任务已启动", message: `任务 ${code} 已启动` });
    },
    onError: (error: unknown) => {
      addToast({ type: "error", title: "启动失败", message: getErrorMessage(error, "请稍后重试") });
    },
  });
}

// 启用任务 Hook
export function useEnableTask() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (code: string) => taskApi.enable(code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.list() });
      addToast({ type: "success", title: "启用成功", message: "任务已启用" });
    },
    onError: (error: unknown) => {
      addToast({ type: "error", title: "操作失败", message: getErrorMessage(error, "请稍后重试") });
    },
  });
}

// 禁用任务 Hook
export function useDisableTask() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (code: string) => taskApi.disable(code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.list() });
      addToast({ type: "success", title: "禁用成功", message: "任务已禁用" });
    },
    onError: (error: unknown) => {
      addToast({ type: "error", title: "操作失败", message: getErrorMessage(error, "请稍后重试") });
    },
  });
}
