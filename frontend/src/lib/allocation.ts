import type { Position } from "@/types/position";
import { largestRemainderPercents } from "@/lib/utils";

/**
 * 资产大类聚合（issue #99）：饼图图例与持仓分区头共用的单一计算入口。
 *
 * 大类口径：股票/债券/黄金/现金/在途/其他。
 * - IN_TRANSIT_BUY/SELL（asset_type=cash）抽出为独立「在途」类，不与现金混合；
 * - CASH 行及其余 asset_type=cash 行归「现金」；
 * - 基金行 asset_type 存的就是中文大类名（股票/债券/黄金），缺省归「其他」。
 */

export const IN_TRANSIT_CODES = new Set(["IN_TRANSIT_BUY", "IN_TRANSIT_SELL"]);

/** 大类色板（对齐预览稿）：股票 blue / 债券 violet / 黄金 amber / 现金 slate-400 / 在途 slate-300 */
export const ASSET_TYPE_COLORS: Record<string, string> = {
  股票: "#3b82f6",
  债券: "#8b5cf6",
  黄金: "#f59e0b",
  现金: "#94a3b8",
  在途: "#cbd5e1",
  其他: "#64748b",
};

/** 大类展示顺序 */
export const CATEGORY_ORDER = ["股票", "债券", "黄金", "现金", "在途", "其他"];

export interface AllocationItem {
  /** 大类名（股票/债券/黄金/现金/在途/其他） */
  key: string;
  /** 市值合计（元） */
  value: number;
  /** 占比（%）：最大余数法，全部项加总恒为 100.0 */
  percent: number;
  color: string;
}

/** 持仓行金额：净值型取 market_value，现金/在途行取 cash_amount（快照中两者一致） */
export function positionAmount(p: Position): number {
  return p.market_value ?? p.cash_amount ?? 0;
}

/** 持仓行 → 资产大类 */
export function categoryOf(p: Position): string {
  if (IN_TRANSIT_CODES.has(p.product_code)) return "在途";
  if (p.product_code === "CASH" || p.asset_type === "cash") return "现金";
  return p.asset_type || "其他";
}

/**
 * 行级占比（最大余数法，与传入 positions 顺序对齐）。
 * 全部行加总恒为 100.0%；分区/图例/卡片均由它加总，杜绝 ±0.1% 漂移。
 */
export function buildRowPercents(positions: Position[]): number[] {
  return largestRemainderPercents(positions.map((p) => positionAmount(p)));
}

/** 按资产大类聚合持仓（大类占比 = 行级占比加总，与分区头/卡片严格自洽） */
export function buildAllocation(positions: Position[]): AllocationItem[] {
  const rowPercents = buildRowPercents(positions);
  const byCategory = new Map<string, { value: number; percent: number }>();
  positions.forEach((p, i) => {
    const cat = categoryOf(p);
    const cur = byCategory.get(cat) ?? { value: 0, percent: 0 };
    cur.value += positionAmount(p);
    cur.percent += rowPercents[i];
    byCategory.set(cat, cur);
  });
  const cats = [...byCategory.keys()].sort(
    (a, b) => CATEGORY_ORDER.indexOf(a) - CATEGORY_ORDER.indexOf(b)
  );
  return cats.map((c) => ({
    key: c,
    value: byCategory.get(c)?.value ?? 0,
    percent: byCategory.get(c)?.percent ?? 0,
    color: ASSET_TYPE_COLORS[c] ?? ASSET_TYPE_COLORS["其他"],
  }));
}
