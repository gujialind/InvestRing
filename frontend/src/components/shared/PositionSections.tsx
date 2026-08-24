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
import type { AssetClassificationItem } from "@/types/asset-classification";
import { assetClassColor, IN_TRANSIT_COLOR, OTHER_COLOR } from "@/lib/colors";
import {
  PSEUDO_IN_TRANSIT_CODE,
  PSEUDO_OTHER_CODE,
  buildRowPercents,
  categoryCodeOf,
  positionAmount,
} from "@/lib/allocation";
import { formatNumber, getReturnColorClass } from "@/lib/utils";
import { resolveSubDim, type SubDimension } from "@/lib/dimensions";

interface PositionSectionsProps {
  positions: Position[];
  /** asset_class 维度字典（分区顺序/颜色/二级分组维度由此驱动，issue #128） */
  assetClasses: AssetClassificationItem[];
  /** 分区头右侧操作位（如桌面端「管理持仓」按钮） */
  action?: ReactNode;
  /** 组合级二级分组维度覆盖（issue #144，portfolio.display_config 契约原样传入）：
   * 仅存显式覆盖项，缺键/未传/null 时经 resolveSubDim fallback 内置默认 */
  displayConfig?: Record<string, string> | null;
}

function formatProfit(value: number | null | undefined): string {
  if (value === null || value === undefined) return "--";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${formatNumber(value)}`;
}

/** 单个持仓行卡片（白底 + slate-200 边框 + 8px 圆角，#109 V4 定稿）
 * row1=产品全称（15px/600；名目统一由上方 chip 承载，卡片不再出现维度名）
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
            {(position.nav_lag_days ?? 0) > 0 && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-3 w-3 cursor-help" />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-[240px]">
                    按 T-{position.nav_lag_days} 交易日净值估值，日收益相应滞后
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
 * 分类持仓分区（issue #99，双端复用；#128 维度化）：
 * 按资产大类分组（分区顺序/颜色由 asset_class 字典 sort_order 驱动），
 * IN_TRANSIT 在途行抽出为独立「在途资金」卡片（仅金额+占比，无收益列）。
 * 占比全部来自行级最大余数法，分区头 = 行占比加总，与饼图图例严格自洽。
 *
 * 维度二级分组（承 #109 V4 定稿 + #114 修正，#128 起数据源从 asset_name
 * 换成维度 name）：分区内按维度值子分组（股票→region、债券/商品→segment、
 * 现金平铺），分组 chip 始终位于产品名之上（与大类同名时不渲染 chip、
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
 * 分区内按维度 name 二级分组（#128，维度名做参数不写死）：
 * dim=null 时平铺（单组、组名=大类名，与大类同名不渲染 chip）；
 * 组间按合计市值降序、未分类恒垫底；组内卡片按市值降序。
 */
function groupRowsByDimension(
  rows: Row[],
  dim: SubDimension | null,
  fallbackName: string
): AssetGroup[] {
  const nameKey = dim ? (`${dim}_name` as const) : null;
  const byName = new Map<string, Row[]>();
  for (const r of rows) {
    const name = nameKey ? r.position[nameKey] ?? "未分类" : fallbackName;
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

export default function PositionSections({ positions, assetClasses, action, displayConfig }: PositionSectionsProps) {
  if (!positions.length) {
    return (
      <div className="py-8 text-center text-muted-foreground">暂无持仓记录</div>
    );
  }

  const rowPercents = buildRowPercents(positions);
  const rows = positions.map((p, i) => ({ position: p, percent: rowPercents[i] }));

  const inTransitRows = rows.filter(
    (r) => categoryCodeOf(r.position) === PSEUDO_IN_TRANSIT_CODE
  );
  const normalRows = rows.filter(
    (r) => categoryCodeOf(r.position) !== PSEUDO_IN_TRANSIT_CODE
  );

  // 分区顺序/颜色/二级分组维度全部由 asset_class 字典驱动（sort_order 排序）；
  // 二级维度优先取组合级 display_config 覆盖（issue #144），缺键 fallback 内置默认
  const knownCodes = new Set(assetClasses.map((a) => a.code));
  const sections: {
    name: string;
    color: string;
    subDim: SubDimension | null;
    rows: Row[];
  }[] = [];
  for (const ac of [...assetClasses].sort((a, b) => a.sort_order - b.sort_order)) {
    const sectionRows = normalRows.filter(
      (r) => categoryCodeOf(r.position) === ac.code
    );
    if (sectionRows.length) {
      sections.push({
        name: ac.name,
        color: assetClassColor(ac.sort_order),
        subDim: resolveSubDim(displayConfig, ac.code),
        rows: sectionRows,
      });
    }
  }
  // 「其他」兜底分区：派生缺失或字典未收录的行（固定垫底，平铺不分组）
  const otherRows = normalRows.filter((r) => {
    const c = categoryCodeOf(r.position);
    return c === PSEUDO_OTHER_CODE || !knownCodes.has(c);
  });
  if (otherRows.length) {
    sections.push({ name: "其他", color: OTHER_COLOR, subDim: null, rows: otherRows });
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
              {groupRowsByDimension(section.rows, section.subDim, section.name).map((g) => {
                // V4 定稿 + #114 修正：分组 chip 始终位于产品名之上，仅组名与
                // 大类同名（平铺组）时不渲染 chip；chip 行合计恒显示
                const showChip = g.name !== section.name;
                return (
                  <div key={g.name} data-testid="asset-group">
                    {showChip && (
                      <div
                        data-testid="asset-group-header"
                        className="mb-2 flex items-center justify-between px-0.5"
                      >
                        {/* 维度分组 chip：neutral 底 + 大类色小圆点（#127，色点取 lib/colors 分类色） */}
                        <span className="inline-flex items-center rounded bg-muted px-2 py-0.5 text-xs font-semibold text-foreground-secondary">
                          <span
                            className="mr-1.5 h-1.5 w-1.5 rounded-full"
                            style={{ background: section.color }}
                          />
                          {g.name}
                        </span>
                        {/* 分组 chip 行占比取整（同大类分区头口径） */}
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
                style={{ background: IN_TRANSIT_COLOR }}
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
