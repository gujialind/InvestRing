"use client";

import MainLayout from "@/components/layout/MainLayout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCurrency, formatPercent, formatReturnRate, getReturnColorClass } from "@/lib/utils";
import { TrendingUp, TrendingDown, Wallet, Users, Briefcase, Loader2 } from "lucide-react";
import { usePortfolioList } from "@/hooks/usePortfolio";
import { useSubscriptionList } from "@/hooks/useTrade";
import { useInvestorList } from "@/hooks/useInvestor";
import Link from "next/link";

export default function DashboardPage() {
  const { data: portfoliosData, isLoading: portfoliosLoading } = usePortfolioList({ page_size: 100 });
  const { data: subscriptionsData, isLoading: subscriptionsLoading } = useSubscriptionList({ page_size: 5 });
  const { data: investorsData, isLoading: investorsLoading } = useInvestorList({ page_size: 100 });

  const portfolios = portfoliosData?.items || [];
  const subscriptions = subscriptionsData?.items || [];
  const investors = investorsData?.items || [];

  // 计算统计数据
  const activePortfolios = portfolios.filter(p => p.status === "active");
  const totalValue = activePortfolios.reduce((sum, p) => {
    // 如果有快照数据，使用快照的 total_value
    return sum + (p.total_value || 0);
  }, 0);

  // 计算平均累计收益（基于有收益数据的组合）
  const portfoliosWithReturn = activePortfolios.filter(p => p.cumulative_return !== undefined && p.cumulative_return !== null);
  const avgReturn = portfoliosWithReturn.length > 0
    ? portfoliosWithReturn.reduce((sum, p) => sum + (p.cumulative_return || 0), 0) / portfoliosWithReturn.length
    : 0;

  const isLoading = portfoliosLoading || subscriptionsLoading || investorsLoading;

  if (isLoading) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center h-[60vh]">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
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
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                总资产
              </CardTitle>
              <Wallet className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatCurrency(totalValue)}
              </div>
              <p className="text-xs text-muted-foreground">
                {activePortfolios.length} 个活跃组合合计
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                平均累计收益
              </CardTitle>
              <TrendingUp className="h-4 w-4 text-green-500" />
            </CardHeader>
            <CardContent>
              <div className={`text-2xl font-bold ${getReturnColorClass(avgReturn)}`}>
                {formatReturnRate(avgReturn)}
              </div>
              <p className="text-xs text-muted-foreground">
                活跃组合平均值
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                活跃组合
              </CardTitle>
              <Briefcase className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {activePortfolios.length}
              </div>
              <p className="text-xs text-muted-foreground">
                共 {portfolios.length} 个组合
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                投资人
              </CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {investors.length}
              </div>
              <p className="text-xs text-muted-foreground">
                系统注册投资人
              </p>
            </CardContent>
          </Card>
        </div>

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
              <div className="text-center text-muted-foreground py-8">
                暂无活跃组合，请先创建组合
              </div>
            ) : (
              <div className="space-y-4">
                {activePortfolios.map((portfolio) => (
                  <Link
                    key={portfolio.code}
                    href={`/portfolios/${portfolio.code}`}
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
              <div className="text-center text-muted-foreground py-8">
                暂无交易记录
              </div>
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
