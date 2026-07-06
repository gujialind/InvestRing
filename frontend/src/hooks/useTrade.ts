"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { tradeApi, subscriptionApi, getErrorMessage, ApiException } from "@/lib/api";
import { TradeCreate, TradeUpdate } from "@/types/trade";
import { SubscriptionCreate } from "@/types/subscription";
import { useUIStore } from "@/stores/uiStore";

const TRADE_QUERY_KEY = "trades";
const SUBSCRIPTION_QUERY_KEY = "subscriptions";

// ==================== 调仓交易 Hooks ====================

// 交易列表 Hook
export function useTradeList(
  params?: {
    page?: number;
    page_size?: number;
    portfolio_code?: string;
    status?: string;
  }
) {
  return useQuery({
    queryKey: [TRADE_QUERY_KEY, "list", params],
    queryFn: () => tradeApi.list(params),
    staleTime: 30 * 1000,
  });
}

// 单个交易详情 Hook
export function useTrade(id: number) {
  return useQuery({
    queryKey: [TRADE_QUERY_KEY, id],
    queryFn: () => tradeApi.get(id),
    enabled: !!id && id > 0,
    staleTime: 30 * 1000,
  });
}

// 创建交易 Hook
export function useCreateTrade() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (data: TradeCreate) => tradeApi.create(data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [TRADE_QUERY_KEY, "list"] });
      queryClient.invalidateQueries({
        queryKey: ["portfolios", data.portfolio_code],
      });
      queryClient.invalidateQueries({
        queryKey: ["positions", data.portfolio_code],
      });
      addToast({
        type: "success",
        title: "交易创建成功",
        message: `${data.trade_type === "buy" ? "买入" : "卖出"} 申请已提交`,
      });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "交易创建失败",
        message: getErrorMessage(error, "请检查可用份额/现金是否充足"),
      });
    },
  });
}

// 更新交易 Hook
export function useUpdateTrade(id: number) {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (data: TradeUpdate) => tradeApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [TRADE_QUERY_KEY, id] });
      queryClient.invalidateQueries({ queryKey: [TRADE_QUERY_KEY, "list"] });
      addToast({
        type: "success",
        title: "更新成功",
        message: "交易信息已更新",
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

// 确认交易 Hook
export function useConfirmTrade() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data?: { confirm_date?: string; price?: number } }) =>
      tradeApi.confirm(id, data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [TRADE_QUERY_KEY, data.id] });
      queryClient.invalidateQueries({ queryKey: [TRADE_QUERY_KEY, "list"] });
      queryClient.invalidateQueries({
        queryKey: ["portfolios", data.portfolio_code],
      });
      queryClient.invalidateQueries({
        queryKey: ["positions", data.portfolio_code],
      });
      addToast({
        type: "success",
        title: "确认成功",
        message: "交易已确认",
      });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "确认失败",
        message: getErrorMessage(error, "请检查确认日期和价格"),
      });
    },
  });
}

// 取消交易 Hook
export function useCancelTrade() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (id: number) => tradeApi.cancel(id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [TRADE_QUERY_KEY, data.id] });
      queryClient.invalidateQueries({ queryKey: [TRADE_QUERY_KEY, "list"] });
      queryClient.invalidateQueries({
        queryKey: ["portfolios", data.portfolio_code],
      });
      addToast({
        type: "success",
        title: "取消成功",
        message: "交易已取消",
      });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "取消失败",
        message: getErrorMessage(error, "该交易状态不允许取消"),
      });
    },
  });
}

// 取消确认交易 Hook
export function useUnconfirmTrade() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (id: number) => tradeApi.unconfirm(id),
    onSuccess: (data, id) => {
      queryClient.invalidateQueries({ queryKey: [TRADE_QUERY_KEY, id] });
      queryClient.invalidateQueries({ queryKey: [TRADE_QUERY_KEY, "list"] });
      addToast({
        type: "success",
        title: "取消确认成功",
        message: "交易已取消确认，可以修改或删除",
      });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "取消确认失败",
        message: getErrorMessage(error, "操作失败，请重试"),
      });
    },
  });
}

// 删除交易 Hook
export function useDeleteTrade() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => tradeApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [TRADE_QUERY_KEY, "list"] });
    },
  });
}

// 批量调仓 Hook
export function useBatchRebalance() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: ({
      portfolioCode,
      trades,
      idempotencyKey,
    }: {
      portfolioCode: string;
      trades: TradeCreate[];
      idempotencyKey?: string;
    }) => tradeApi.batchRebalance(portfolioCode, trades, idempotencyKey),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: [TRADE_QUERY_KEY, "list"] });
      queryClient.invalidateQueries({
        queryKey: ["portfolios", variables.portfolioCode],
      });
      queryClient.invalidateQueries({
        queryKey: ["positions", variables.portfolioCode],
      });
      addToast({
        type: "success",
        title: "批量调仓成功",
        message: `已创建 ${data.created_trades.length} 笔交易`,
      });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "批量调仓失败",
        message: getErrorMessage(error, "请检查可用现金和份额"),
      });
    },
  });
}

// ==================== 申购赎回 Hooks ====================

// 申购赎回列表 Hook
export function useSubscriptionList(
  params?: {
    page?: number;
    page_size?: number;
    portfolio_code?: string;
    status?: string;
  }
) {
  return useQuery({
    queryKey: [SUBSCRIPTION_QUERY_KEY, "list", params],
    queryFn: () => subscriptionApi.list(params),
    staleTime: 30 * 1000,
  });
}

// 单个申购赎回详情 Hook
export function useSubscription(id: number) {
  return useQuery({
    queryKey: [SUBSCRIPTION_QUERY_KEY, id],
    queryFn: () => subscriptionApi.get(id),
    enabled: !!id && id > 0,
    staleTime: 30 * 1000,
  });
}

// 创建申购赎回 Hook
export function useCreateSubscription() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (data: SubscriptionCreate) => subscriptionApi.create(data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [SUBSCRIPTION_QUERY_KEY, "list"] });
      queryClient.invalidateQueries({
        queryKey: ["portfolios", data.portfolio_code],
      });
      addToast({
        type: "success",
        title: "申请提交成功",
        message: `${data.sub_type === "subscribe" ? "申购" : "赎回"} 申请已提交`,
      });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "申请提交失败",
        message: getErrorMessage(error, "请检查输入信息"),
      });
    },
  });
}

// 确认申购赎回 Hook
export function useConfirmSubscription() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number;
    }) => subscriptionApi.confirm(id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [SUBSCRIPTION_QUERY_KEY, data.id] });
      queryClient.invalidateQueries({ queryKey: [SUBSCRIPTION_QUERY_KEY, "list"] });
      queryClient.invalidateQueries({
        queryKey: ["portfolios", data.portfolio_code],
      });
      addToast({
        type: "success",
        title: "确认成功",
        message: `${data.sub_type === "subscribe" ? "申购" : "赎回"} 已确认`,
      });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "确认失败",
        message: getErrorMessage(error, "请检查确认信息"),
      });
    },
  });
}

// 取消申购赎回 Hook
export function useCancelSubscription() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (id: number) => subscriptionApi.cancel(id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [SUBSCRIPTION_QUERY_KEY, data.id] });
      queryClient.invalidateQueries({ queryKey: [SUBSCRIPTION_QUERY_KEY, "list"] });
      queryClient.invalidateQueries({
        queryKey: ["portfolios", data.portfolio_code],
      });
      addToast({
        type: "success",
        title: "取消成功",
        message: "申请已取消",
      });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "取消失败",
        message: getErrorMessage(error, "该申请状态不允许取消"),
      });
    },
  });
}

// 取消确认申购赎回 Hook
export function useUnconfirmSubscription() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (id: number) => subscriptionApi.unconfirm(id),
    onSuccess: (data, id) => {
      queryClient.invalidateQueries({ queryKey: [SUBSCRIPTION_QUERY_KEY, id] });
      queryClient.invalidateQueries({ queryKey: [SUBSCRIPTION_QUERY_KEY, "list"] });
      addToast({
        type: "success",
        title: "取消确认成功",
        message: "申购赎回事件已取消确认，可以修改或删除",
      });
    },
    onError: (error: unknown) => {
      // SNAPSHOT_DEPENDENCY: 快照已纳入该申购，需先删除快照
      if (error instanceof ApiException && error.code === "SNAPSHOT_DEPENDENCY") {
        addToast({
          type: "error",
          title: "快照依赖冲突",
          message: error.message,
        });
        return;
      }
      addToast({
        type: "error",
        title: "取消确认失败",
        message: getErrorMessage(error, "操作失败，请重试"),
      });
    },
  });
}
