"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatNumber, formatSharesUnit } from "@/lib/utils";

export interface PortfolioInvestorItem {
  investor_code: string;
  name: string;
  shares: number;
}

interface PortfolioInvestorsListProps {
  investors?: PortfolioInvestorItem[];
  /** 组合总份额（最新快照），用于计算占比 */
  totalShares?: number;
}

/**
 * 组合投资人列表（issue #99，双端复用）：
 * 从桌面详情页内联 Tab 抽出，供 ?tab=investors 视图（双端）使用。
 */
export default function PortfolioInvestorsList({
  investors,
  totalShares = 0,
}: PortfolioInvestorsListProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>投资人列表</CardTitle>
        <CardDescription>组合中的投资人及份额</CardDescription>
      </CardHeader>
      <CardContent>
        {!investors || investors.length === 0 ? (
          <div className="py-8 text-center text-muted-foreground">暂无投资人</div>
        ) : (
          <div className="space-y-4">
            {investors.map((investor) => (
              <div
                key={investor.investor_code}
                className="flex items-center justify-between rounded-lg border p-4"
              >
                <div>
                  <p className="font-medium">{investor.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {investor.investor_code}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-medium">{formatSharesUnit(investor.shares)}</p>
                  <p className="text-sm text-muted-foreground">
                    占比:{" "}
                    {totalShares > 0
                      ? formatNumber((investor.shares / totalShares) * 100, 2)
                      : "0.00"}
                    %
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
