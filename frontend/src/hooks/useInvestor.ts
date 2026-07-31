"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { investorApi, getErrorMessage } from "@/lib/api";
import { InvestorCreate, InvestorUpdate } from "@/types/investor";
import { useUIStore } from "@/stores/uiStore";

const INVESTOR_QUERY_KEY = "investors";

// 投资人列表 Hook
export function useInvestorList(params?: { page?: number; page_size?: number }) {
  return useQuery({
    queryKey: [INVESTOR_QUERY_KEY, "list", params],
    queryFn: () => investorApi.list(params),
    staleTime: 30 * 1000,
  });
}

// 单个投资人详情 Hook
export function useInvestor(code: string) {
  return useQuery({
    queryKey: [INVESTOR_QUERY_KEY, code],
    queryFn: () => investorApi.get(code),
    enabled: !!code,
    staleTime: 30 * 1000,
  });
}

// 创建投资人 Hook
export function useCreateInvestor() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (data: InvestorCreate) => investorApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [INVESTOR_QUERY_KEY, "list"] });
      addToast({
        type: "success",
        title: "创建成功",
        message: "投资人已创建",
      });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "创建失败",
        message: getErrorMessage(error, "请检查输入信息"),
      });
    },
  });
}

// 更新投资人 Hook（code 随 mutate 传入，避免闭包捕获空 code 导致请求打到错误 URL）
export function useUpdateInvestor() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: ({ code, data }: { code: string; data: InvestorUpdate }) =>
      investorApi.update(code, data),
    onSuccess: (_, { code }) => {
      queryClient.invalidateQueries({ queryKey: [INVESTOR_QUERY_KEY, code] });
      queryClient.invalidateQueries({ queryKey: [INVESTOR_QUERY_KEY, "list"] });
      addToast({
        type: "success",
        title: "更新成功",
        message: "投资人信息已更新",
      });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "更新失败",
        message: getErrorMessage(error, "请稍后重试"),
      });
    },
  });
}

// 移除投资人 Hook
export function useRemoveInvestor() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (code: string) => investorApi.remove(code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [INVESTOR_QUERY_KEY, "list"] });
      addToast({
        type: "success",
        title: "移除成功",
        message: "投资人已移除",
      });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "移除失败",
        message: getErrorMessage(error, "该投资人仍持有份额，无法移除"),
      });
    },
  });
}
