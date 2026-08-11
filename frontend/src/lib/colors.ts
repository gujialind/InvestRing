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
 * 资产大类配色：饼图（buildAllocation）与持仓分区共用。
 * 现金用低饱和灰蓝、在途用天蓝（现金的轻量态）、其他用深灰蓝。
 */
export const ASSET_TYPE_COLORS: Record<string, string> = {
  股票: CHART_COLORS[0],
  债券: CHART_COLORS[3],
  黄金: CHART_COLORS[1],
  现金: CHART_COLORS[6],
  在途: CHART_COLORS[2],
  其他: CHART_COLORS[7],
};

/** 交易方向标识色（仅用于买/卖小圆点，不表达涨跌）：买入 = C1 靛蓝，卖出 = C6 赭橙 */
export const TRADE_DIRECTION_COLORS = {
  buy: CHART_COLORS[0],
  sell: CHART_COLORS[5],
} as const;
