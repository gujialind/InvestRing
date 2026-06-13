"use client";

import MobileLayout from "@/components/mobile/MobileLayout";
import { Card, CardContent } from "@/components/ui/card";
import { formatCurrency, formatReturnRate, getReturnColorClass } from "@/lib/utils";
import { TrendingUp, Wallet, Users, Briefcase, Loader2 } from "lucide-react";
import { usePortfolioList } from "@/hooks/usePortfolio";
import { useSubscriptionList } from "@/hooks/useTrade";
import { useInvestorList } from "@/hooks/useInvestor";
import Link from "next/link";

export default function MobileDashboardPage() {
  const { data: portfoliosData, isLoading: portfoliosLoading } = usePortfolioList({ page_size: 100 });
  const { data: subscriptionsData, isLoading: subscriptionsLoading } = useSubscriptionList({ page_size: 5 });
  const { data: investorsData, isLoading: investorsLoading } = useInvestorList({ page_size: 100 });

  const portfolios = portfoliosData?.items || [];
  const subscriptions = subscriptionsData?.items || [];
  const investors = investorsData?.items || [];

  // Calculate stats
  const activePortfolios = portfolios.filter(p => p.status === "active");
  const totalValue = activePortfolios.reduce((sum, p) => sum + (p.total_value || 0), 0);

  const portfoliosWithReturn = activePortfolios.filter(p => p.cumulative_return !== undefined && p.cumulative_return !== null);
  const avgReturn = portfoliosWithReturn.length > 0
    ? portfoliosWithReturn.reduce((sum, p) => sum + (p.cumulative_return || 0), 0) / portfoliosWithReturn.length
    : 0;

  const isLoading = portfoliosLoading || subscriptionsLoading || investorsLoading;

  if (isLoading) {
    return (
      <MobileLayout>
        <div className="flex items-center justify-center h-[60vh]">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </MobileLayout>
    );
  }

  return (
    <MobileLayout>
      <div className="space-y-4 p-4">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold">首页</h1>
          <p className="text-sm text-muted-foreground">投资组合概览</p>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 gap-3">
          <Card>
            <CardContent className="p-3">
              <div className="flex items-center gap-2 mb-1">
                <Wallet className="h-4 w-4 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">总资产</span>
              </div>
              <div className="text-lg font-bold">{formatCurrency(totalValue)}</div>
              <p className="text-xs text-muted-foreground mt-1">
                {activePortfolios.length} 个活跃组合
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-3">
              <div className="flex items-center gap-2 mb-1">
                <TrendingUp className="h-4 w-4 text-red-500" />
                <span className="text-xs text-muted-foreground">平均收益</span>
              </div>
              <div className={`text-lg font-bold ${getReturnColorClass(avgReturn)}`}>
                {formatReturnRate(avgReturn)}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                活跃组合平均
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-3">
              <div className="flex items-center gap-2 mb-1">
                <Briefcase className="h-4 w-4 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">活跃组合</span>
              </div>
              <div className="text-lg font-bold">{activePortfolios.length}</div>
              <p className="text-xs text-muted-foreground mt-1">
                共 {portfolios.length} 个
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-3">
              <div className="flex items-center gap-2 mb-1">
                <Users className="h-4 w-4 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">投资人</span>
              </div>
              <div className="text-lg font-bold">{investors.length}</div>
              <p className="text-xs text-muted-foreground mt-1">
                系统注册
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Pending Transactions Alert */}
        {subscriptions.filter(s => s.status === "pending").length > 0 && (
          <Card className="bg-yellow-50 border-yellow-200">
            <CardContent className="p-3">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-yellow-500"></div>
                <span className="text-sm font-medium text-yellow-800">
                  {subscriptions.filter(s => s.status === "pending").length} 笔待确认交易
                </span>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Active Portfolios List */}
        <div>
          <h2 className="text-base font-semibold mb-3">活跃组合</h2>
          {activePortfolios.length === 0 ? (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                暂无活跃组合，请先创建组合
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2">
              {activePortfolios.map((portfolio) => (
                <Link key={portfolio.code} href={`/m/portfolio/${portfolio.code}`}>
                  <Card className="hover:bg-accent transition-colors">
                    <CardContent className="p-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium text-sm">{portfolio.name}</p>
                          <p className="text-xs text-muted-foreground">{portfolio.code}</p>
                        </div>
                        <div className="text-right">
                          <p className="font-medium text-sm">{formatCurrency(portfolio.total_value || 0)}</p>
                          <p className={`text-xs ${getReturnColorClass(portfolio.cumulative_return || 0)}`}>
                            {formatReturnRate(portfolio.cumulative_return || 0)}
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Recent Activity */}
        {subscriptions.length > 0 && (
          <div>
            <h2 className="text-base font-semibold mb-3">最近交易</h2>
            <div className="space-y-2">
              {subscriptions.slice(0, 5).map((sub) => (
                <Card key={sub.id}>
                  <CardContent className="p-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium">
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
                        <p className="text-xs text-muted-foreground">
                          {sub.portfolio_code} | {sub.investor_code}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-medium">
                          {sub.sub_type === "subscribe"
                            ? formatCurrency(sub.amount || 0)
                            : `${sub.shares?.toLocaleString() || 0} 份`
                          }
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {sub.apply_date}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}
      </div>
    </MobileLayout>
  );
}
