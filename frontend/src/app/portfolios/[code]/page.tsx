"use client";

import { useParams, useRouter } from "next/navigation";
import MainLayout from "@/components/layout/MainLayout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { formatCurrency, formatReturnRate, formatNumber, getReturnColorClass } from "@/lib/utils";
import { TrendingUp, Users, Wallet, ArrowLeft, Loader2, PowerOff, Power, Trash2, Plus } from "lucide-react";
import Link from "next/link";
import { usePortfolio, useLatestSnapshot, usePortfolioInvestors, useClosePortfolio, useActivatePortfolio, useDeletePortfolio } from "@/hooks/usePortfolio";
import { usePositionList } from "@/hooks/usePortfolio";
import { useRoleCheck } from "@/hooks/useAuth";

export default function PortfolioDetailPage() {
  const params = useParams();
  const router = useRouter();
  const code = params.code as string;

  const { data: portfolio, isLoading: portfolioLoading } = usePortfolio(code);
  const { data: snapshot, isLoading: snapshotLoading } = useLatestSnapshot(code);
  const { data: investors, isLoading: investorsLoading } = usePortfolioInvestors(code);
  const { data: positionsData, isLoading: positionsLoading } = usePositionList(code, { page_size: 100 });
  const closePortfolio = useClosePortfolio();
  const activatePortfolio = useActivatePortfolio();
  const deletePortfolio = useDeletePortfolio();
  const { isAdmin } = useRoleCheck();

  const positions = positionsData?.items || [];
  const isLoading = portfolioLoading || snapshotLoading || investorsLoading || positionsLoading;

  if (isLoading) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center h-[60vh]">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </MainLayout>
    );
  }

  if (!portfolio) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <p className="text-muted-foreground">组合不存在</p>
          <Link href="/portfolios">
            <Button variant="outline" className="mt-4">
              <ArrowLeft className="mr-2 h-4 w-4" />
              返回列表
            </Button>
          </Link>
        </div>
      </MainLayout>
    );
  }

  const totalValue = snapshot?.total_value || 0;
  const totalShares = snapshot?.total_shares || 0;
  const unitPrice = snapshot?.unit_price || 0;

  const isDraft = portfolio.status === "draft";
  const isActive = portfolio.status === "active";
  const isClosed = portfolio.status === "closed";

  const handleClose = () => {
    if (confirm("确定要关闭该组合吗？关闭后无法再进行申购/赎回/调仓操作。")) {
      closePortfolio.mutate(code);
    }
  };

  const handleActivate = () => {
    if (confirm("确定要重新激活该组合吗？")) {
      activatePortfolio.mutate(code);
    }
  };

  const handleDelete = () => {
    if (confirm("确定要删除该组合吗？删除后不可恢复。")) {
      deletePortfolio.mutate(code, {
        onSuccess: () => router.push("/portfolios"),
      });
    }
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/portfolios">
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
            <div className="flex gap-2">
              {isDraft && (
                <>
                  <Link href={`/portfolios/${code}/subscriptions`}>
                    <Button>
                      <Plus className="mr-2 h-4 w-4" />
                      首次申购激活
                    </Button>
                  </Link>
                  <Button variant="outline" onClick={handleDelete} disabled={deletePortfolio.isPending}>
                    <Trash2 className="mr-2 h-4 w-4 text-red-500" />
                    删除组合
                  </Button>
                </>
              )}
              {isActive && (
                <Button variant="outline" onClick={handleClose} disabled={closePortfolio.isPending}>
                  <PowerOff className="mr-2 h-4 w-4 text-red-500" />
                  关闭组合
                </Button>
              )}
              {isClosed && (
                <Button variant="outline" onClick={handleActivate} disabled={activatePortfolio.isPending}>
                  <Power className="mr-2 h-4 w-4 text-green-500" />
                  重新激活
                </Button>
              )}
            </div>
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
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">总资产</CardTitle>
                <Wallet className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{formatCurrency(totalValue)}</div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">净值</CardTitle>
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{formatNumber(unitPrice, 4)}</div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">累计收益</CardTitle>
                <TrendingUp className="h-4 w-4 text-green-500" />
              </CardHeader>
              <CardContent>
                <div className={`text-2xl font-bold ${getReturnColorClass(portfolio.cumulative_return || 0)}`}>
                  {formatReturnRate(portfolio.cumulative_return || 0)}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">总份额</CardTitle>
                <Users className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {formatNumber(totalShares, 2)}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        <Tabs defaultValue="overview" className="space-y-4">
          <TabsList>
            <TabsTrigger value="overview">概览</TabsTrigger>
            {!isDraft && <TabsTrigger value="positions">持仓</TabsTrigger>}
            {!isDraft && <TabsTrigger value="investors">投资人</TabsTrigger>}
            {!isDraft && <TabsTrigger value="nav">净值历史</TabsTrigger>}
          </TabsList>

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
              <CardHeader>
                <CardTitle>持仓列表</CardTitle>
                <CardDescription>当前持仓明细</CardDescription>
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
                            金额: {formatCurrency(position.amount || 0)}
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
                    {investors.map((investor: any) => (
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
                <div className="h-[300px] flex items-center justify-center text-muted-foreground">
                  净值曲线图将在此处显示
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </MainLayout>
  );
}
