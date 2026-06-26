"use client";

import MainLayout from "@/components/layout/MainLayout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCurrency, formatReturnRate, getReturnColorClass } from "@/lib/utils";
import { ArrowRightLeft } from "lucide-react";
import Link from "next/link";
import { useDashboardStats } from "@/hooks/useDashboardStats";
import DashboardStatsCards from "@/components/shared/DashboardStatsCards";
import LoadingState from "@/components/shared/LoadingState";
import EmptyState from "@/components/shared/EmptyState";

export default function DashboardPage() {
  const {
    portfolios,
    activePortfolios,
    subscriptions,
    trades,
    investors,
    totalValue,
    avgReturn,
    pendingSubscriptions,
    pendingTrades,
    isLoading,
  } = useDashboardStats();

  if (isLoading) {
    return (
      <MainLayout>
        <LoadingState />
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">首页</h1>
          <p className="text-muted-foreground">
            投资组合概览和净值曲线
          </p>
        </div>

        {/* Summary Cards */}
        <DashboardStatsCards
          totalValue={totalValue}
          avgReturn={avgReturn}
          activeCount={activePortfolios.length}
          totalCount={portfolios.length}
          investorCount={investors.length}
          variant="desktop"
        />

        {/* Pending Transactions Alerts */}
        {pendingSubscriptions.length > 0 && (
          <Card className="bg-yellow-50 border-yellow-200">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-yellow-800 flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-yellow-500"></div>
                待确认交易提醒
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {pendingSubscriptions.slice(0, 3).map((sub) => (
                  <div key={sub.id} className="flex items-center justify-between text-sm">
                    <span className="text-yellow-800">
                      {sub.sub_type === "subscribe" ? "申购" : "赎回"} - {sub.portfolio_code}
                    </span>
                    <span className="text-yellow-700 font-mono tabular-nums">
                      {sub.sub_type === "subscribe"
                        ? formatCurrency(sub.amount || 0)
                        : `${sub.shares?.toLocaleString() || 0} 份`
                      }
                    </span>
                  </div>
                ))}
                {pendingSubscriptions.length > 3 && (
                  <p className="text-xs text-yellow-600 text-center">
                    还有 {pendingSubscriptions.length - 3} 笔待确认交易
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Pending Trades Alert */}
        {pendingTrades.length > 0 && (
          <Card className="bg-blue-50 border-blue-200">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-blue-800 flex items-center gap-2">
                <ArrowRightLeft className="h-4 w-4 text-blue-600" />
                待确认调仓交易
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {pendingTrades.slice(0, 3).map((trade) => (
                  <div key={trade.id} className="flex items-center justify-between text-sm">
                    <span className="text-blue-800">
                      {trade.trade_type === "buy" ? "买入" : "卖出"} - {trade.product_code}
                    </span>
                    <span className="text-blue-700 font-mono tabular-nums">
                      {trade.trade_type === "buy"
                        ? formatCurrency(trade.amount || 0)
                        : `${trade.shares?.toLocaleString() || 0} 份`
                      }
                    </span>
                  </div>
                ))}
                {pendingTrades.length > 3 && (
                  <p className="text-xs text-blue-600 text-center">
                    还有 {pendingTrades.length - 3} 笔待确认调仓
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Active Portfolios Table */}
        <Card>
          <CardHeader>
            <CardTitle>活跃组合</CardTitle>
            <CardDescription>
              当前活跃的投资组合列表
            </CardDescription>
          </CardHeader>
          <CardContent>
            {activePortfolios.length === 0 ? (
              <EmptyState message="暂无活跃组合，请先创建组合" />
            ) : (
              <div className="space-y-4">
                {activePortfolios.map((portfolio) => (
                  <Link
                    key={portfolio.code}
                    href={`/portfolio/${portfolio.code}`}
                    className="flex items-center justify-between p-4 border rounded-lg hover:bg-accent transition-colors"
                  >
                    <div>
                      <p className="font-medium">{portfolio.name}</p>
                      <p className="text-sm text-muted-foreground">{portfolio.code}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-medium">{formatCurrency(portfolio.total_value || 0)}</p>
                      <p className={`text-sm ${getReturnColorClass(portfolio.cumulative_return || 0)}`}>
                        {formatReturnRate(portfolio.cumulative_return || 0)}
                      </p>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card>
          <CardHeader>
            <CardTitle>最近交易</CardTitle>
            <CardDescription>
              最近的投资操作记录
            </CardDescription>
          </CardHeader>
          <CardContent>
            {subscriptions.length === 0 ? (
              <EmptyState message="暂无交易记录" />
            ) : (
              <div className="space-y-4">
                {subscriptions.map((sub) => (
                  <div key={sub.id} className="flex items-center justify-between p-4 border rounded-lg">
                    <div>
                      <p className="font-medium">
                        {sub.sub_type === "subscribe" ? "申购" : "赎回"}
                        <span className={`ml-2 text-xs px-2 py-0.5 rounded-full ${
                          sub.status === "pending"
                            ? "bg-yellow-100 text-yellow-800"
                            : sub.status === "confirmed"
                            ? "bg-green-100 text-green-800"
                            : "bg-gray-100 text-gray-800"
                        }`}>
                          {sub.status === "pending" ? "待确认" : sub.status === "confirmed" ? "已确认" : "已取消"}
                        </span>
                      </p>
                      <p className="text-sm text-muted-foreground">
                        组合: {sub.portfolio_code} | 投资人: {sub.investor_code}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-medium">
                        {sub.sub_type === "subscribe"
                          ? formatCurrency(sub.amount || 0)
                          : `${sub.shares?.toLocaleString() || 0} 份`
                        }
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {sub.apply_date}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}
