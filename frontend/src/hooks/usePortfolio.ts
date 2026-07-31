"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { portfolioApi, positionApi, getErrorMessage } from "@/lib/api";
import { PortfolioCreate, PortfolioUpdate } from "@/types/portfolio";
import { useUIStore } from "@/stores/uiStore";

const PORTFOLIO_QUERY_KEY = "portfolios";
const POSITION_QUERY_KEY = "positions";
const SNAPSHOT_QUERY_KEY = "snapshots";

// 组合列表 Hook
export function usePortfolioList(params?: { page?: number; page_size?: number; status?: string }) {
  return useQuery({
    queryKey: [PORTFOLIO_QUERY_KEY, "list", params],
    queryFn: () => portfolioApi.list(params),
    staleTime: 30 * 1000,
  });
}

// 单个组合详情 Hook
export function usePortfolio(code: string) {
  return useQuery({
    queryKey: [PORTFOLIO_QUERY_KEY, code],
    queryFn: () => portfolioApi.get(code),
    enabled: !!code,
    staleTime: 30 * 1000,
  });
}

// 创建组合 Hook
export function useCreatePortfolio() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (data: PortfolioCreate) => portfolioApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PORTFOLIO_QUERY_KEY, "list"] });
      addToast({
        type: "success",
        title: "创建成功",
        message: "组合已创建",
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

// 更新组合 Hook
export function useUpdatePortfolio(code: string) {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (data: PortfolioUpdate) => portfolioApi.update(code, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PORTFOLIO_QUERY_KEY, code] });
      queryClient.invalidateQueries({ queryKey: [PORTFOLIO_QUERY_KEY, "list"] });
      addToast({
        type: "success",
        title: "更新成功",
        message: "组合信息已更新",
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

// 关闭组合 Hook
export function useClosePortfolio() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (code: string) => portfolioApi.close(code),
    onSuccess: (_, code) => {
      queryClient.invalidateQueries({ queryKey: [PORTFOLIO_QUERY_KEY, code] });
      queryClient.invalidateQueries({ queryKey: [PORTFOLIO_QUERY_KEY, "list"] });
      addToast({
        type: "success",
        title: "关闭成功",
        message: "组合已关闭",
      });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "关闭失败",
        message: getErrorMessage(error, "请确保无待处理交易"),
      });
    },
  });
}

// 激活组合 Hook
export function useActivatePortfolio() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (code: string) => portfolioApi.activate(code),
    onSuccess: (_, code) => {
      queryClient.invalidateQueries({ queryKey: [PORTFOLIO_QUERY_KEY, code] });
      queryClient.invalidateQueries({ queryKey: [PORTFOLIO_QUERY_KEY, "list"] });
      addToast({
        type: "success",
        title: "激活成功",
        message: "组合已重新激活",
      });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "激活失败",
        message: getErrorMessage(error, "请稍后重试"),
      });
    },
  });
}

// 注：后端不提供 DELETE /portfolios/{code}（外键 RESTRICT，生命周期由关闭/重新激活管理），
// 故不提供删除组合 Hook。

// 最新净值快照 Hook
export function useLatestSnapshot(code: string) {
  return useQuery({
    queryKey: [PORTFOLIO_QUERY_KEY, code, SNAPSHOT_QUERY_KEY, "latest"],
    queryFn: () => portfolioApi.getLatestSnapshot(code),
    enabled: !!code,
    staleTime: 30 * 1000,
  });
}

// 可用现金 Hook
export function useAvailableCash(code: string) {
  return useQuery({
    queryKey: [PORTFOLIO_QUERY_KEY, code, "available-cash"],
    queryFn: () => portfolioApi.getAvailableCash(code),
    enabled: !!code,
    staleTime: 10 * 1000,
  });
}

// 组合投资人列表 Hook
export function usePortfolioInvestors(code: string) {
  return useQuery({
    queryKey: [PORTFOLIO_QUERY_KEY, code, "investors"],
    queryFn: () => portfolioApi.getInvestors(code),
    enabled: !!code,
    staleTime: 30 * 1000,
  });
}

// ==================== 持仓相关 Hooks ====================

// 持仓列表 Hook
export function usePositionList(
  portfolioCode: string,
  params?: { page?: number; page_size?: number; snapshot_date?: string }
) {
  return useQuery({
    queryKey: [POSITION_QUERY_KEY, portfolioCode, "list", params],
    queryFn: () => positionApi.list(portfolioCode, params),
    enabled: !!portfolioCode,
    staleTime: 30 * 1000,
  });
}
