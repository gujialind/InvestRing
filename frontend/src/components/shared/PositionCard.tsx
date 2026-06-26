"use client";

import { Card, CardContent } from "@/components/ui/card";
import { formatCurrency, formatNumber, formatReturnRate, getReturnColorClass } from "@/lib/utils";

interface PositionCardProps {
  productCode: string;
  productName?: string;
  market?: string;
  shares?: number;
  costPrice?: number;
  currentPrice?: number;
  marketValue?: number;
  profitLoss?: number;
  profitLossPercent?: number;
  onClick?: () => void;
}

export default function PositionCard({
  productCode,
  productName,
  market,
  shares,
  costPrice,
  currentPrice,
  marketValue,
  profitLoss,
  profitLossPercent,
  onClick,
}: PositionCardProps) {
  return (
    <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={onClick}>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium">{productName || productCode}</p>
            <p className="text-xs text-muted-foreground">
              {productCode}
              {market ? ` | ${market}` : ""}
            </p>
          </div>
          {profitLoss !== undefined && profitLoss !== null && (
            <span
              className={`text-sm font-medium ${
                getReturnColorClass(profitLoss)
              }`}
            >
              {profitLoss >= 0 ? "+" : ""}
              {formatReturnRate(profitLossPercent ?? 0)}
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2 text-sm">
          {shares !== undefined && (
            <>
              <span className="text-muted-foreground">份额</span>
              <span className="text-right font-mono tabular-nums">{formatNumber(shares)}</span>
            </>
          )}
          {costPrice !== undefined && (
            <>
              <span className="text-muted-foreground">成本价</span>
              <span className="text-right font-mono tabular-nums">{formatCurrency(costPrice)}</span>
            </>
          )}
          {currentPrice !== undefined && (
            <>
              <span className="text-muted-foreground">当前价</span>
              <span className="text-right font-mono tabular-nums">{formatCurrency(currentPrice)}</span>
            </>
          )}
          {marketValue !== undefined && (
            <>
              <span className="text-muted-foreground">市值</span>
              <span className="text-right font-medium font-mono tabular-nums">{formatCurrency(marketValue)}</span>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}