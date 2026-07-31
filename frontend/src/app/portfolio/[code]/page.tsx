"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import MainLayout from "@/components/layout/MainLayout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { formatCurrency, formatNumber, formatReturnRate, getReturnColorClass } from "@/lib/utils";
import { ArrowLeft, RefreshCw } from "lucide-react";
import Link from "next/link";
import {
  usePortfolio,
  useLatestSnapshot,
  usePortfolioInvestors,
  usePositionList,
  useClosePortfolio,
  useActivatePortfolio,
} from "@/hooks/usePortfolio";
import { useRoleCheck } from "@/hooks/useAuth";
import NavCurve from "@/components/charts/NavCurve";
import PortfolioStatsCards from "@/components/shared/PortfolioStatsCards";
import PortfolioActionButtons from "@/components/shared/PortfolioActionButtons";
import ClosePortfolioDialog from "@/components/shared/dialogs/ClosePortfolioDialog";
import LoadingState from "@/components/shared/LoadingState";
import EmptyState from "@/components/shared/EmptyState";

export default function PortfolioDetailPage() {
  const params = useParams();
  const code = params.code as string;

  const { data: portfolio, isLoading: portfolioLoading } = usePortfolio(code);
  const { data: snapshot, isLoading: snapshotLoading } = useLatestSnapshot(code);
  const { data: investors, isLoading: investorsLoading } = usePortfolioInvestors(code);
  const { data: positionsData, isLoading: positionsLoading } = usePositionList(code, { page_size: 100 });
  const closePortfolio = useClosePortfolio();
  const activatePortfolio = useActivatePortfolio();
  const { isAdmin } = useRoleCheck();

  const positions = positionsData?.items || [];
  const isLoading = portfolioLoading || snapshotLoading || investorsLoading || positionsLoading;

  const [showCloseDialog, setShowCloseDialog] = useState(false);
  const [returnType, setReturnType] = useState<"cumulative" | "annualized" | "twr">("twr");

  if (isLoading) {
    return (
      <MainLayout>
        <LoadingState />
      </MainLayout>
    );
  }

  if (!portfolio) {
    return (
      <MainLayout>
        <EmptyState
          message="组合不存在"
          action={
            <Link href="/portfolio">
              <Button variant="outline">
                <ArrowLeft className="mr-2 h-4 w-4" />
                返回列表
              </Button>
            </Link>
          }
        />
      </MainLayout>
    );
  }

  const totalValue = snapshot?.total_value || 0;
  const totalShares = snapshot?.total_shares || 0;
  const unitPrice = snapshot?.unit_price || 0;

  const isDraft = portfolio.status === "draft";

  const handleClose = () => {
    closePortfolio.mutate(code, {
      onSuccess: () => setShowCloseDialog(false),
    });
  };

  const handleActivate = () => {
    activatePortfolio.mutate(code);
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/portfolio">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <div>
              <h1 className="text-3xl font-bold tracking-tight">{portfolio.name}</h1>
              <p className="text-muted-foreground">{portfolio.code}</p>
            </div>
          </div>
          {isAdmin && (
            <PortfolioActionButtons
              portfolioCode={code}
              status={portfolio.status as "draft" | "active" | "closed"}
              basePath="/portfolio"
              variant="desktop"
              onCloseClick={() => setShowCloseDialog(true)}
              onActivateClick={handleActivate}
              isClosePending={closePortfolio.isPending}
              isActivatePending={activatePortfolio.isPending}
            />
          )}
        </div>

        {isDraft && (
          <Alert>
            <AlertDescription>
              组合尚未激活，请执行首次申购以启动组合。初始净值固定为 1.0000
            </AlertDescription>
          </Alert>
        )}

        {!isDraft && (
          <div className="space-y-4">
            {/* Stats Cards */}
            <PortfolioStatsCards
              totalValue={totalValue}
              unitPrice={unitPrice}
              totalShares={totalShares}
              cumulativeReturn={portfolio.cumulative_return || 0}
              variant="desktop"
            />

            {/* Return Type Switcher */}
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-medium">收益率类型</span>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant={returnType === "cumulative" ? "default" : "outline"}
                      onClick={() => setReturnType("cumulative")}
                      className="text-xs"
                    >
                      累计收益
                    </Button>
                    <Button
                      size="sm"
                      variant={returnType === "annualized" ? "default" : "outline"}
                      onClick={() => setReturnType("annualized")}
                      className="text-xs"
                    >
                      年化收益
                    </Button>
                    <Button
                      size="sm"
                      variant={returnType === "twr" ? "default" : "outline"}
                      onClick={() => setReturnType("twr")}
                      className="text-xs"
                    >
                      时间加权
                    </Button>
                  </div>
                </div>
                <div className="text-center py-4">
                  <div className={`text-3xl font-bold ${getReturnColorClass(portfolio.cumulative_return || 0)}`}>
                    {formatReturnRate(portfolio.cumulative_return || 0)}
                  </div>
                  <p className="text-sm text-muted-foreground mt-2">
                    {returnType === "cumulative" && "累计收益率：从组合成立至今的总收益"}
                    {returnType === "annualized" && "年化收益率：按年计算的复合收益率"}
                    {returnType === "twr" && "时间加权收益率：消除资金流影响的收益率（默认）"}
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        <Tabs defaultValue="overview" className="space-y-4">
          <div className="flex items-center gap-2">
            <TabsList>
              <TabsTrigger value="overview">概览</TabsTrigger>
              {!isDraft && <TabsTrigger value="positions">持仓</TabsTrigger>}
              {!isDraft && <TabsTrigger value="investors">投资人</TabsTrigger>}
              {!isDraft && <TabsTrigger value="nav">净值历史</TabsTrigger>}
            </TabsList>
            {/* 快照管理是独立页面而非 Tab：不能用 Link 包 TabsTrigger，
                首次点击会被 Tabs 激活逻辑拦截导致需点两次才能进入 */}
            {isAdmin && !isDraft && (
              <Link href={`/portfolio/${code}/snapshots`}>
                <Button variant="outline" size="sm">快照管理</Button>
              </Link>
            )}
          </div>

          <TabsContent value="overview" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>组合信息</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">状态</span>
                  <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    portfolio.status === "active"
                      ? "bg-green-100 text-green-800"
                      : portfolio.status === "draft"
                      ? "bg-yellow-100 text-yellow-800"
                      : "bg-gray-100 text-gray-800"
                  }`}>
                    {portfolio.status === "active" ? "活跃" : portfolio.status === "draft" ? "草稿" : "已关闭"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">描述</span>
                  <span>{portfolio.description || "--"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">成立日期</span>
                  <span>{portfolio.started_at ? portfolio.started_at.split("T")[0] : "--"}</span>
                </div>
                {!isDraft && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">最新快照日期</span>
                    <span>{snapshot?.snapshot_date || "--"}</span>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="positions" className="space-y-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>持仓列表</CardTitle>
                  <CardDescription>当前持仓明细</CardDescription>
                </div>
                {isAdmin && !isDraft && (
                  <Link href={`/portfolio/${code}/positions`}>
                    <Button variant="outline" size="sm">
                      <RefreshCw className="mr-2 h-4 w-4" />
                      管理持仓
                    </Button>
                  </Link>
                )}
              </CardHeader>
              <CardContent>
                {positions.length === 0 ? (
                  <div className="text-center text-muted-foreground py-8">
                    暂无持仓记录
                  </div>
                ) : (
                  <div className="space-y-4">
                    {positions.map((position) => (
                      <div key={position.id} className="flex items-center justify-between p-4 border rounded-lg">
                        <div>
                          <p className="font-medium">{position.product_code}</p>
                          <p className="text-sm text-muted-foreground">
                            {position.market || "--"} {position.platform_code ? `| ${position.platform_code}` : ""}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="font-medium">{formatNumber(position.shares || 0, 2)} 份</p>
                          <p className="text-sm text-muted-foreground">
                            金额: {formatCurrency(position.cash_amount || 0)}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="investors" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>投资人列表</CardTitle>
                <CardDescription>组合中的投资人及份额</CardDescription>
              </CardHeader>
              <CardContent>
                {!investors || investors.length === 0 ? (
                  <div className="text-center text-muted-foreground py-8">
                    暂无投资人
                  </div>
                ) : (
                  <div className="space-y-4">
                    {investors.map((investor) => (
                      <div key={investor.investor_code} className="flex items-center justify-between p-4 border rounded-lg">
                        <div>
                          <p className="font-medium">{investor.name}</p>
                          <p className="text-sm text-muted-foreground">{investor.investor_code}</p>
                        </div>
                        <div className="text-right">
                          <p className="font-medium">{formatNumber(investor.shares || 0, 2)} 份</p>
                          <p className="text-sm text-muted-foreground">
                            占比: {totalShares > 0 ? ((investor.shares || 0) / totalShares * 100).toFixed(2) : 0}%
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="nav" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>净值历史</CardTitle>
                <CardDescription>组合净值走势</CardDescription>
              </CardHeader>
              <CardContent>
                {snapshot ? (
                  <NavCurve
                    data={[{
                      date: snapshot.snapshot_date,
                      nav: snapshot.unit_price
                    }]}
                    initialNav={1.0000}
                  />
                ) : (
                  <div className="h-[300px] flex items-center justify-center text-muted-foreground">
                    暂无净值数据
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      <ClosePortfolioDialog
        open={showCloseDialog}
        onOpenChange={setShowCloseDialog}
        onConfirm={handleClose}
        isPending={closePortfolio.isPending}
        positions={positions}
        investors={investors}
      />
    </MainLayout>
  );
}
