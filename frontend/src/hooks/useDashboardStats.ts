"use client";

import { usePortfolioList } from "./usePortfolio";
import { useSubscriptionList, useTradeList } from "./useTrade";
import { useInvestorList } from "./useInvestor";
import { Portfolio } from "@/types/portfolio";
import { Subscription } from "@/types/subscription";
import { Trade } from "@/types/trade";
import { Investor } from "@/types/investor";

export interface DashboardStats {
  portfolios: Portfolio[];
  activePortfolios: Portfolio[];
  subscriptions: Subscription[];
  trades: Trade[];
  investors: Investor[];
  totalValue: number;
  avgReturn: number;
  pendingSubscriptions: Subscription[];
  pendingTrades: Trade[];
  isLoading: boolean;
}

/**
 * 首页仪表盘统计聚合 hook。
 * 桌面端与移动端共用同一数据源与计算逻辑，仅渲染层各自实现。
 */
export function useDashboardStats(): DashboardStats {
  const { data: portfoliosData, isLoading: portfoliosLoading } = usePortfolioList({ page_size: 100 });
  const { data: subscriptionsData, isLoading: subscriptionsLoading } = useSubscriptionList({ page_size: 100 });
  const { data: tradesData, isLoading: tradesLoading } = useTradeList({ page_size: 100 });
  const { data: investorsData, isLoading: investorsLoading } = useInvestorList({ page_size: 100 });

  const portfolios = portfoliosData?.items || [];
  const subscriptions = subscriptionsData?.items || [];
  const trades = tradesData?.items || [];
  const investors = investorsData?.items || [];

  const activePortfolios = portfolios.filter((p) => p.status === "active");
  const totalValue = activePortfolios.reduce((sum, p) => sum + (p.total_value || 0), 0);

  const portfoliosWithReturn = activePortfolios.filter(
    (p) => p.cumulative_return !== undefined && p.cumulative_return !== null
  );
  const avgReturn =
    portfoliosWithReturn.length > 0
      ? portfoliosWithReturn.reduce((sum, p) => sum + (p.cumulative_return || 0), 0) /
        portfoliosWithReturn.length
      : 0;

  const pendingSubscriptions = subscriptions.filter((s) => s.status === "pending");
  const pendingTrades = trades.filter((t) => t.status === "pending");

  return {
    portfolios,
    activePortfolios,
    subscriptions,
    trades,
    investors,
    totalValue,
    avgReturn,
    pendingSubscriptions,
    pendingTrades,
    isLoading: portfoliosLoading || subscriptionsLoading || tradesLoading || investorsLoading,
  };
}
