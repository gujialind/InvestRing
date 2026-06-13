"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import MobileLayout from "@/components/mobile/MobileLayout";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { formatCurrency, formatReturnRate, formatNumber, getReturnColorClass } from "@/lib/utils";
import { TrendingUp, Users, Wallet, ArrowLeft, Loader2, PowerOff, Power, Trash2, Plus, ArrowRightLeft } from "lucide-react";
import Link from "next/link";
import { usePortfolio, useLatestSnapshot, useClosePortfolio, useActivatePortfolio, useDeletePortfolio } from "@/hooks/usePortfolio";
import { useRoleCheck } from "@/hooks/useAuth";
import NavCurveSimple from "@/components/charts/NavCurveSimple";

export default function MobilePortfolioDetailPage() {
  const params = useParams();
  const router = useRouter();
  const code = params.code as string;

  const { data: portfolio, isLoading: portfolioLoading } = usePortfolio(code);
  const { data: snapshot, isLoading: snapshotLoading } = useLatestSnapshot(code);
  const closePortfolio = useClosePortfolio();
  const activatePortfolio = useActivatePortfolio();
  const deletePortfolio = useDeletePortfolio();
  const { isAdmin } = useRoleCheck();

  const isLoading = portfolioLoading || snapshotLoading;

  const [showCloseDialog, setShowCloseDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  if (isLoading) {
    return (
      <MobileLayout>
        <div className="flex items-center justify-center h-[60vh]">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </MobileLayout>
    );
  }

  if (!portfolio) {
    return (
      <MobileLayout>
        <div className="text-center py-12 px-4">
          <p className="text-muted-foreground">组合不存在</p>
          <Link href="/m/portfolio">
            <Button variant="outline" className="mt-4">
              <ArrowLeft className="mr-2 h-4 w-4" />
              返回列表
            </Button>
          </Link>
        </div>
      </MobileLayout>
    );
  }

  const totalValue = snapshot?.total_value || 0;
  const totalShares = snapshot?.total_shares || 0;
  const unitPrice = snapshot?.unit_price || 0;

  const isDraft = portfolio.status === "draft";
  const isActive = portfolio.status === "active";
  const isClosed = portfolio.status === "closed";

  const handleClose = () => {
    closePortfolio.mutate(code, {
      onSuccess: () => setShowCloseDialog(false),
    });
  };

  const handleActivate = () => {
    if (confirm("确定要重新激活该组合吗？")) {
      activatePortfolio.mutate(code);
    }
  };

  const handleDelete = () => {
    deletePortfolio.mutate(code, {
      onSuccess: () => {
        setShowDeleteDialog(false);
        router.push("/m/portfolio");
      },
    });
  };

  return (
    <MobileLayout>
      <div className="space-y-4 p-4">
        {/* Header */}
        <div className="flex items-center gap-3">
          <Link href="/m/portfolio">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div className="flex-1">
            <h1 className="text-xl font-bold">{portfolio.name}</h1>
            <p className="text-xs text-muted-foreground">{portfolio.code}</p>
          </div>
        </div>

        {/* Status Alert */}
        {isDraft && (
          <Alert>
            <AlertDescription>
              组合尚未激活，请执行首次申购以启动组合。初始净值固定为 1.0000
            </AlertDescription>
          </Alert>
        )}

        {/* Stats Cards - Simplified for mobile */}
        {!isDraft && (
          <div className="grid grid-cols-2 gap-3">
            <Card>
              <CardContent className="p-3">
                <div className="flex items-center gap-2 mb-1">
                  <Wallet className="h-4 w-4 text-muted-foreground" />
                  <span className="text-xs text-muted-foreground">总资产</span>
                </div>
                <div className="text-lg font-bold">{formatCurrency(totalValue)}</div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-3">
                <div className="flex items-center gap-2 mb-1">
                  <TrendingUp className="h-4 w-4 text-muted-foreground" />
                  <span className="text-xs text-muted-foreground">净值</span>
                </div>
                <div className="text-lg font-bold">{formatNumber(unitPrice, 4)}</div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-3">
                <div className="flex items-center gap-2 mb-1">
                  <TrendingUp className="h-4 w-4 text-red-500" />
                  <span className="text-xs text-muted-foreground">累计收益</span>
                </div>
                <div className={`text-lg font-bold ${getReturnColorClass(portfolio.cumulative_return || 0)}`}>
                  {formatReturnRate(portfolio.cumulative_return || 0)}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-3">
                <div className="flex items-center gap-2 mb-1">
                  <Users className="h-4 w-4 text-muted-foreground" />
                  <span className="text-xs text-muted-foreground">总份额</span>
                </div>
                <div className="text-lg font-bold">
                  {formatNumber(totalShares, 2)}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Action Buttons */}
        {isAdmin && (
          <div className="grid grid-cols-2 gap-2">
            {isDraft && (
              <>
                <Link href={`/m/portfolio/${code}/subscriptions`}>
                  <Button className="w-full">
                    <Plus className="mr-2 h-4 w-4" />
                    首次申购
                  </Button>
                </Link>
                <Button variant="outline" onClick={() => setShowDeleteDialog(true)} disabled={deletePortfolio.isPending}>
                  <Trash2 className="mr-2 h-4 w-4 text-red-500" />
                  删除
                </Button>
              </>
            )}
            {isActive && (
              <>
                <Link href={`/m/portfolio/${code}/subscriptions`}>
                  <Button className="w-full">
                    <Plus className="mr-2 h-4 w-4" />
                    申购赎回
                  </Button>
                </Link>
                <Link href={`/m/portfolio/${code}/trades`}>
                  <Button variant="outline" className="w-full">
                    <ArrowRightLeft className="mr-2 h-4 w-4" />
                    调仓
                  </Button>
                </Link>
              </>
            )}
            {isClosed && (
              <Button variant="outline" onClick={handleActivate} disabled={activatePortfolio.isPending} className="col-span-2">
                <Power className="mr-2 h-4 w-4 text-green-500" />
                重新激活
              </Button>
            )}
          </div>
        )}

        {/* NAV Chart - Simplified for mobile */}
        {!isDraft && snapshot && (
          <Card>
            <CardContent className="p-4">
              <h3 className="text-sm font-medium mb-3">净值走势</h3>
              <NavCurveSimple
                data={[{
                  date: snapshot.snapshot_date,
                  nav: snapshot.unit_price
                }]}
                height={200}
              />
            </CardContent>
          </Card>
        )}

        {/* Quick Links */}
        {!isDraft && (
          <Card>
            <CardContent className="p-4 space-y-2">
              <Link href={`/m/portfolio/${code}/positions`}>
                <Button variant="ghost" className="w-full justify-start">
                  <Wallet className="mr-2 h-4 w-4" />
                  持仓管理
                </Button>
              </Link>
              <Link href={`/m/portfolio/${code}/subscriptions`}>
                <Button variant="ghost" className="w-full justify-start">
                  <Plus className="mr-2 h-4 w-4" />
                  申购赎回记录
                </Button>
              </Link>
              <Link href={`/m/portfolio/${code}/trades`}>
                <Button variant="ghost" className="w-full justify-start">
                  <ArrowRightLeft className="mr-2 h-4 w-4" />
                  调仓交易记录
                </Button>
              </Link>
            </CardContent>
          </Card>
        )}
      </div>
    </MobileLayout>
  );
}
