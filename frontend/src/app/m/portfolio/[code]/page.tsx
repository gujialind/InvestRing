"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ArrowLeft, Wallet, Plus, ArrowRightLeft } from "lucide-react";
import Link from "next/link";
import { usePortfolio, useLatestSnapshot, useClosePortfolio, useActivatePortfolio } from "@/hooks/usePortfolio";
import { useRoleCheck } from "@/hooks/useAuth";
import NavCurveSimple from "@/components/charts/NavCurveSimple";
import PortfolioStatsCards from "@/components/shared/PortfolioStatsCards";
import PortfolioActionButtons from "@/components/shared/PortfolioActionButtons";
import ClosePortfolioDialog from "@/components/shared/dialogs/ClosePortfolioDialog";
import LoadingState from "@/components/shared/LoadingState";
import EmptyState from "@/components/shared/EmptyState";

export default function MobilePortfolioDetailPage() {
  const params = useParams();
  const code = params.code as string;

  const { data: portfolio, isLoading: portfolioLoading } = usePortfolio(code);
  const { data: snapshot, isLoading: snapshotLoading } = useLatestSnapshot(code);
  const closePortfolio = useClosePortfolio();
  const activatePortfolio = useActivatePortfolio();
  const { isAdmin } = useRoleCheck();

  const isLoading = portfolioLoading || snapshotLoading;

  const [showCloseDialog, setShowCloseDialog] = useState(false);

  if (isLoading) {
    return (
      <LoadingState />
    );
  }

  if (!portfolio) {
    return (
      <EmptyState
        message="组合不存在"
        action={
          <Link href="/m/portfolio">
            <Button variant="outline">
              <ArrowLeft className="mr-2 h-4 w-4" />
              返回列表
            </Button>
          </Link>
        }
      />
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
    <>
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
        <PortfolioStatsCards
          totalValue={totalValue}
          unitPrice={unitPrice}
          totalShares={totalShares}
          cumulativeReturn={portfolio.cumulative_return || 0}
          variant="mobile"
        />
      )}

      {/* Action Buttons */}
      {isAdmin && (
        <PortfolioActionButtons
          portfolioCode={code}
          status={portfolio.status as "draft" | "active" | "closed"}
          basePath="/m/portfolio"
          variant="mobile"
          onCloseClick={() => setShowCloseDialog(true)}
          onActivateClick={handleActivate}
          isClosePending={closePortfolio.isPending}
          isActivatePending={activatePortfolio.isPending}
        />
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

    <ClosePortfolioDialog
      open={showCloseDialog}
      onOpenChange={setShowCloseDialog}
      onConfirm={handleClose}
      isPending={closePortfolio.isPending}
      positions={[]}
    />
    </>
  );
}
