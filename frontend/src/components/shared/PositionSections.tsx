"use client";

import type { ReactNode } from "react";
import { Info } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { Position } from "@/types/position";
import {
  ASSET_TYPE_COLORS,
  CATEGORY_ORDER,
  buildRowPercents,
  categoryOf,
  positionAmount,
} from "@/lib/allocation";
import { formatNumber, getReturnColorClass } from "@/lib/utils";

interface PositionSectionsProps {
  positions: Position[];
  /** 分区头右侧操作位（如桌面端「管理持仓」按钮） */
  action?: ReactNode;
}

function formatProfit(value: number | null | undefined): string {
  if (value === null || value === undefined) return "--";
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatNumber(value)}`;
}

/** 单个持仓行卡片（白底 + slate-200 边框 + 8px 圆角，对齐预览稿）
 * row1=资产短名目+金额+占比 row2=产品全称+代码+平台徽标
 * 收益行三列：持仓金额 | 累计收益 | 最新收益(MM-DD) */
function PositionCard({
  position,
  percent,
}: {
  position: Position;
  percent: number;
}) {
  const amount = positionAmount(position);
  const mmdd = position.snapshot_date
    ? position.snapshot_date.slice(5, 10).replace("-", "/")
    : "";
  return (
    <div className="bg-white border border-slate-200 rounded-lg px-4 py-3">
      {/* row1: 资产短名目 + 金额 + 占比 */}
      <div className="flex items-baseline justify-between">
        <span className="text-[15px] font-semibold">
          {position.asset_name || position.product_name || position.product_code}
        </span>
        <span className="text-sm font-semibold tabular-nums text-slate-900">
          {formatNumber(amount)} 元
          <span className="ml-1.5 font-normal text-slate-500">
            {percent.toFixed(1)}%
          </span>
        </span>
      </div>
      {/* row2: 产品全称 + 代码 + 平台徽标 */}
      <div className="mt-1 flex items-center gap-2">
        <span className="text-xs text-slate-500 truncate">
          {position.product_name || position.product_code}
        </span>
        <span className="text-xs text-slate-400 tabular-nums">
          {position.product_code}
        </span>
        {(position.platform_name || position.platform_code) && (
          <span className="ml-auto rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600 flex-shrink-0">
            {position.platform_name || position.platform_code}
          </span>
        )}
      </div>
      {/* 收益行三列：持仓金额 | 累计收益 | 最新收益(MM-DD) */}
      <div className="mt-2.5 flex border-t border-slate-100 pt-2.5">
        <div className="flex-1">
          <div className="text-xs text-slate-500">持仓金额</div>
          <div className="mt-0.5 text-base font-bold tabular-nums text-slate-900">
            {formatNumber(amount)}
          </div>
        </div>
        <div className="flex-1">
          <div className="text-xs text-slate-500">累计收益</div>
          <div
            className={`mt-0.5 text-base font-bold tabular-nums ${getReturnColorClass(
              position.profit_loss
            )}`}
          >
            {formatProfit(position.profit_loss)}
          </div>
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-1 text-xs text-slate-500">
            {mmdd ? `最新收益 (${mmdd})` : "最新收益"}
            {position.is_qdii && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-3 w-3 cursor-help" />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-[240px]">
                    QDII 按 T-1 净值估值，日收益滞后一天
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>
          <div
            className={`mt-0.5 text-base font-bold tabular-nums ${getReturnColorClass(
              position.daily_profit
            )}`}
          >
            {formatProfit(position.daily_profit)}
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * 分类持仓分区（issue #99，双端复用）：
 * 按资产大类分组（股票/债券/黄金/现金），IN_TRANSIT 在途行抽出为独立
 * 「在途资金」卡片（仅金额+占比，无收益列）。占比全部来自行级最大余数法，
 * 分区头 = 行占比加总，与饼图图例严格自洽。
 */
export default function PositionSections({ positions, action }: PositionSectionsProps) {
  if (!positions.length) {
    return (
      <div className="py-8 text-center text-muted-foreground">暂无持仓记录</div>
    );
  }

  const rowPercents = buildRowPercents(positions);
  const rows = positions.map((p, i) => ({ position: p, percent: rowPercents[i] }));

  const inTransitRows = rows.filter((r) => categoryOf(r.position) === "在途");
  const normalRows = rows.filter((r) => categoryOf(r.position) !== "在途");

  const sections: { name: string; color: string; rows: typeof rows }[] = [];
  for (const name of CATEGORY_ORDER) {
    if (name === "在途") continue;
    const sectionRows = normalRows.filter((r) => categoryOf(r.position) === name);
    if (sectionRows.length) {
      sections.push({
        name,
        color: ASSET_TYPE_COLORS[name] ?? ASSET_TYPE_COLORS["其他"],
        rows: sectionRows,
      });
    }
  }

  const inTransitTotal = inTransitRows.reduce(
    (s, r) => s + positionAmount(r.position),
    0
  );
  const inTransitPercent = inTransitRows.reduce((s, r) => s + r.percent, 0);

  return (
    <div className="space-y-1">
      {(sections.length > 0 || action) && (
        <div className="flex items-center justify-between">
          <h3 className="text-[15px] font-semibold">持仓明细</h3>
          {action}
        </div>
      )}

      {sections.map((section) => {
        const sectionTotal = section.rows.reduce(
          (s, r) => s + positionAmount(r.position),
          0
        );
        const sectionPercent = section.rows.reduce((s, r) => s + r.percent, 0);
        return (
          <div key={section.name}>
            <div className="flex items-baseline justify-between px-1 pb-2 pt-4">
              <span className="flex items-center text-[15px] font-semibold">
                <span
                  className="mr-1.5 h-2 w-2 rounded-sm"
                  style={{ background: section.color }}
                />
                {section.name}
              </span>
              <span className="text-[17px] font-bold tabular-nums">
                {formatNumber(sectionTotal)}
                <span className="ml-0.5 text-xs font-normal text-slate-500">元</span>
                <span className="ml-1.5 text-[13px] font-normal text-slate-500">
                  {sectionPercent.toFixed(1)}%
                </span>
              </span>
            </div>
            <div className="space-y-2.5">
              {section.rows.map((r) => (
                <PositionCard
                  key={r.position.id}
                  position={r.position}
                  percent={r.percent}
                />
              ))}
            </div>
          </div>
        );
      })}

      {inTransitRows.length > 0 && (
        <div>
          <div className="flex items-baseline justify-between px-1 pb-2 pt-4">
            <span className="flex items-center text-[15px] font-semibold">
              <span
                className="mr-1.5 h-2 w-2 rounded-sm"
                style={{ background: ASSET_TYPE_COLORS["在途"] }}
              />
              在途资金
            </span>
            <span className="text-[17px] font-bold tabular-nums">
              {formatNumber(inTransitTotal)}
              <span className="ml-0.5 text-xs font-normal text-slate-500">元</span>
              <span className="ml-1.5 text-[13px] font-normal text-slate-500">
                {inTransitPercent.toFixed(1)}%
              </span>
            </span>
          </div>
          <div className="space-y-2.5">
            {inTransitRows.map((r) => (
              <div
                key={r.position.id}
                className="bg-white border border-slate-200 rounded-lg px-4 py-3"
              >
                <div className="flex items-baseline justify-between">
                  <span className="text-[15px] font-semibold">
                    {r.position.product_name || r.position.product_code}
                  </span>
                  <span className="text-sm font-semibold tabular-nums text-slate-900">
                    {formatNumber(positionAmount(r.position))} 元
                    <span className="ml-1.5 font-normal text-slate-500">
                      {r.percent.toFixed(1)}%
                    </span>
                  </span>
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <span className="text-xs text-slate-400 tabular-nums">
                    {r.position.product_code}
                  </span>
                  {(r.position.platform_name || r.position.platform_code) && (
                    <span className="ml-auto rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600 flex-shrink-0">
                      {r.position.platform_name || r.position.platform_code}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
