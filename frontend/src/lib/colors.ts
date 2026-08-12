/**
 * 图表与分类色板唯一来源（issue #127，配色方案 v1 §2，决策见 docs/design/visual-spec.md）。
 *
 * 基于 Okabe-Ito 色盲安全色板改造，主动避开 gain 朱红(5°)、loss 松绿(150°)、
 * destructive 绛红(348°) 三个已占用色相，图表元素不会被误读为涨/跌/异常。
 *
 * 红线：组件内禁止出现 hex 字面量；recharts / 内联 style 等必须用 hex 的场景
 * 一律从本文件取色。超过 6 类必须合并为「其他」（CHART_OTHER）。
 */
export const CHART_COLORS = [
  "#2F5FD0", // C1 靛蓝 —— 第一序列色；与品牌/success 同色相是刻意的（品牌一致性）
  "#E8A33D", // C2 琥珀金
  "#56B4E9", // C3 天蓝（Okabe-Ito 原色）
  "#7E69D8", // C4 堇紫
  "#CC79A7", // C5 玫紫（Okabe-Ito 原色）
  "#C9762E", // C6 赭橙 —— 与 C2 靠明度+饱和度区分
  "#8A97AC", // C7 灰蓝 —— 低饱和，专供「其他」合并项
  "#4A5578", // C8 深灰蓝 —— 备用第 8 色 / 次数据线
] as const;

/** 「其他」合并项专用色（= C7 灰蓝） */
export const CHART_OTHER = CHART_COLORS[6];

/** 净值曲线主线（= C1 靛蓝，恒不用红绿；涨跌靠坐标轴数值与 tooltip 的 text-gain/loss 表达） */
export const NAV_LINE = CHART_COLORS[0];

/**
 * 资产大类配色（issue #128 字典驱动）：asset_class 维度字典的 sort_order 即色板
 * 序位，饼图（buildAllocation）与持仓分区共用。保持 #127 配色视觉连续性：
 * 股票=靛蓝、债券=堇紫、商品=琥珀金（承继原「黄金」序位）、现金=灰蓝。
 * 注意：字典 asset_class 的 sort_order 变更即改色。
 */
const ASSET_CLASS_PALETTE = [
  CHART_COLORS[0], // sort_order 1 股票 —— C1 靛蓝
  CHART_COLORS[3], // sort_order 2 债券 —— C4 堇紫
  CHART_COLORS[1], // sort_order 3 商品 —— C2 琥珀金
  CHART_COLORS[6], // sort_order 4 现金 —— C7 灰蓝
] as const;

/** 按 asset_class sort_order 序位取色；序位超出现有 4 大类（未来扩展）兜底深灰蓝 */
export function assetClassColor(sortOrder: number): string {
  return ASSET_CLASS_PALETTE[sortOrder - 1] ?? CHART_COLORS[7];
}

/** 在途资金（伪大类，非字典维度值）：C3 天蓝，现金的轻量态 */
export const IN_TRANSIT_COLOR = CHART_COLORS[2];

/** 其他（伪大类：派生缺失/字典未收录的兜底）：C8 深灰蓝 */
export const OTHER_COLOR = CHART_COLORS[7];

/** 交易方向标识色（仅用于买/卖小圆点，不表达涨跌）：买入 = C1 靛蓝，卖出 = C6 赭橙 */
export const TRADE_DIRECTION_COLORS = {
  buy: CHART_COLORS[0],
  sell: CHART_COLORS[5],
} as const;
