/**
 * 五维正交维度（issue #128 / #135）的共享 UI 常量。
 * 维度字典数据来自 GET /api/asset-classifications，此处放展示标签与
 * 二级分组维度（issue #144）的共享事实来源。
 */

/** 可规则化的四个维度（asset_class 自身不参与规则/适用关联） */
export const RULE_DIMENSIONS = ["region", "style", "size", "segment"] as const;

export type RuleDimension = (typeof RULE_DIMENSIONS)[number];

/** 二级分组维度（= 可规则化四维；内置默认按大类固定，组合级覆盖见 #144） */
export type SubDimension = RuleDimension;

/** 维度字段名（product 表五列） */
export const DIMENSION_FIELDS = {
  region: "region_code",
  style: "style_code",
  size: "size_code",
  segment: "segment_code",
} as const;

export const DIMENSION_LABELS: Record<string, string> = {
  asset_class: "大类",
  region: "地区",
  style: "风格",
  size: "规模",
  segment: "细分",
};

export const RULE_LABELS: Record<string, string> = {
  required: "必填",
  optional: "选填",
};

/** 大类 → 二级分组维度内置默认（issue #128）：股票→地区、债券/商品→细分、现金平铺 */
export const SUB_DIM_BY_CLASS: Record<string, SubDimension | null> = {
  ASSET_STOCK: "region",
  ASSET_BOND: "segment",
  ASSET_COMMODITY: "segment",
  ASSET_CASH: null,
};

/**
 * 合并组合级 display_config 覆盖与内置默认（issue #144）：
 * 覆盖值优先；缺键/未传/未知维度值（防御）回退内置默认。
 */
export function resolveSubDim(
  displayConfig: Record<string, string> | null | undefined,
  classCode: string
): SubDimension | null {
  const override = displayConfig?.[classCode];
  if (override && (RULE_DIMENSIONS as readonly string[]).includes(override)) {
    return override as SubDimension;
  }
  return SUB_DIM_BY_CLASS[classCode] ?? null;
}
