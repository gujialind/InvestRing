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
import { ASSET_TYPE_COLORS } from "@/lib/colors";
import {
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
  const sign = value >= 0 ? "+" : "";
  return `${sign}${formatNumber(value)}`;
}

/** 单个持仓行卡片（白底 + slate-200 边框 + 8px 圆角，#109 V4 定稿）
 * row1=产品全称（15px/600；名目统一由上方 chip 承载，卡片不再出现 asset_name）
 * row2=平台徽标 + 产品代码
 * row3 三列：持仓金额(占比置于数字行下方) | 累计收益 | 最新收益(日期置于数字行下方) */
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
    <div
      data-testid="position-card"
      className="bg-white border border-slate-200 rounded-lg px-4 py-3"
    >
      {/* row1: 产品全称 */}
      <div className="text-[15px] font-semibold">
        {position.product_name || position.product_code}
      </div>
      {/* row2: 平台徽标 + 产品代码 */}
      <div className="mt-1 flex items-center gap-2">
        {(position.platform_name || position.platform_code) && (
          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600 flex-shrink-0">
            {position.platform_name || position.platform_code}
          </span>
        )}
        <span className="text-xs text-slate-400 tabular-nums">
          {position.product_code}
        </span>
      </div>
      {/* row3 三列：持仓金额/占比(下行) | 累计收益 | 最新收益/日期(下行)；
          占比与日期从数字后缀/标签后缀移到数字行下方，缓解小屏横向拥挤 */}
      <div className="mt-2.5 flex border-t border-slate-100 pt-2.5">
        <div className="flex-1">
          <div className="text-xs text-slate-500">持仓金额</div>
          <div className="mt-0.5 text-base font-bold tabular-nums text-slate-900">
            {formatNumber(amount)}
          </div>
          <div className="mt-0.5 text-xs text-slate-500 tabular-nums">
            {percent.toFixed(1)}%
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
          {/* 占位行：与两侧列的下行小字对齐 */}
          <div className="mt-0.5 text-xs invisible">0</div>
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-1 text-xs text-slate-500">
            最新收益
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
          <div className="mt-0.5 text-xs text-slate-500 tabular-nums">
            {mmdd ? `(${mmdd})` : "\u00A0"}
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
 *
 * asset_name 二级聚合（issue #109，V4 定稿，#114 修正）：分区内按 asset_name
 * 子分组，名目 chip 始终位于产品名之上（与大类同名如现金/黄金时不渲染 chip、
 * 卡片平铺），chip 行右侧恒显示市值合计 + 占比合计（无论名下 1 行还是多行，
 * 保证同分区内各 chip 展示口径一致，#114）；chip 组内卡片缩进渲染并带左侧
 * 引导线（空间嵌套）。
 */

type Row = { position: Position; percent: number };

interface AssetGroup {
  name: string;
  rows: Row[];
  total: number;
  percent: number;
}

/**
 * 分区内按 asset_name 二级分组（issue #109）：
 * 组间按合计市值降序、未分类恒垫底；组内卡片按市值降序。
 */
function groupRowsByAssetName(rows: Row[]): AssetGroup[] {
  const byName = new Map<string, Row[]>();
  for (const r of rows) {
    const name = r.position.asset_name ?? "未分类";
    const arr = byName.get(name) ?? [];
    arr.push(r);
    byName.set(name, arr);
  }
  const groups: AssetGroup[] = [...byName.entries()].map(([name, rs]) => {
    const sorted = [...rs].sort(
      (a, b) => positionAmount(b.position) - positionAmount(a.position)
    );
    return {
      name,
      rows: sorted,
      total: sorted.reduce((s, r) => s + positionAmount(r.position), 0),
      percent: sorted.reduce((s, r) => s + r.percent, 0),
    };
  });
  groups.sort((a, b) => {
    if (a.name === "未分类") return 1;
    if (b.name === "未分类") return -1;
    return b.total - a.total;
  });
  return groups;
}

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
              <span className="flex items-center text-[15px] font-bold">
                <span
                  className="mr-1.5 h-2 w-2 rounded-sm"
                  style={{ background: section.color }}
                />
                {section.name}
              </span>
              {/* 大类分区头占比取整（小屏可读性优先，行级/图例仍保留 1 位小数） */}
              <span className="text-[17px] font-bold tabular-nums">
                {formatNumber(sectionTotal)}
                <span className="ml-0.5 text-xs font-normal text-slate-500">元</span>
                <span className="ml-1.5 text-[13px] font-normal text-slate-500">
                  {Math.round(sectionPercent)}%
                </span>
              </span>
            </div>
            <div className="space-y-3">
              {groupRowsByAssetName(section.rows).map((g) => {
                // V4 定稿 + #114 修正：名目 chip 始终位于产品名之上，仅名目与
                // 大类同名（现金/黄金）时不渲染 chip、卡片平铺；chip 行合计恒显示
                const showChip = g.name !== section.name;
                return (
                  <div key={g.name} data-testid="asset-group">
                    {showChip && (
                      <div
                        data-testid="asset-group-header"
                        className="mb-2 flex items-center justify-between px-0.5"
                      >
                        {/* 名目 chip：neutral 底 + 大类色小圆点（#127，色点取 lib/colors 分类色） */}
                        <span className="inline-flex items-center rounded bg-muted px-2 py-0.5 text-xs font-semibold text-foreground-secondary">
                          <span
                            className="mr-1.5 h-1.5 w-1.5 rounded-full"
                            style={{ background: section.color }}
                          />
                          {g.name}
                        </span>
                        {/* 名目 chip 行占比取整（同大类分区头口径） */}
                        <span className="text-sm font-bold tabular-nums">
                          {formatNumber(g.total)}
                          <span className="ml-0.5 text-xs font-normal text-slate-500">
                            元
                          </span>
                          <span className="ml-1.5 text-xs font-normal text-slate-500">
                            {Math.round(g.percent)}%
                          </span>
                        </span>
                      </div>
                    )}
                    {/* chip 组内卡片缩进 + 左侧引导线（空间嵌套）；平铺组不缩进 */}
                    <div
                      className={
                        showChip
                          ? "ml-0.5 space-y-2.5 border-l-2 border-slate-100 pl-3"
                          : "space-y-2.5"
                      }
                    >
                      {g.rows.map((r) => (
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
            </div>
          </div>
        );
      })}

      {inTransitRows.length > 0 && (
        <div>
          <div className="flex items-baseline justify-between px-1 pb-2 pt-4">
            <span className="flex items-center text-[15px] font-bold">
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
                {Math.round(inTransitPercent)}%
              </span>
            </span>
          </div>
          <div className="space-y-2.5">
            {inTransitRows.map((r) => (
              <div
                key={r.position.id}
                data-testid="position-card"
                className="bg-white border border-slate-200 rounded-lg px-4 py-3"
              >
                <div className="text-[15px] font-semibold">
                  {r.position.product_name || r.position.product_code}
                </div>
                <div className="mt-1 flex items-center gap-2">
                  {(r.position.platform_name || r.position.platform_code) && (
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600 flex-shrink-0">
                      {r.position.platform_name || r.position.platform_code}
                    </span>
                  )}
                  <span className="text-xs text-slate-400 tabular-nums">
                    {r.position.product_code}
                  </span>
                </div>
                <div className="mt-2.5 border-t border-slate-100 pt-2.5">
                  <div className="text-xs text-slate-500">持仓金额</div>
                  <div className="mt-0.5 text-base font-bold tabular-nums text-slate-900">
                    {formatNumber(positionAmount(r.position))}
                  </div>
                  {/* 占比与普通卡片一致置于数字行下方 */}
                  <div className="mt-0.5 text-xs text-slate-500 tabular-nums">
                    {r.percent.toFixed(1)}%
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
