/**
 * 五维正交维度（issue #128 / #135）的共享 UI 常量。
 * 维度字典数据来自 GET /api/asset-classifications，此处仅放展示标签。
 */

/** 可规则化的四个维度（asset_class 自身不参与规则/适用关联） */
export const RULE_DIMENSIONS = ["region", "style", "size", "segment"] as const;

export type RuleDimension = (typeof RULE_DIMENSIONS)[number];

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
