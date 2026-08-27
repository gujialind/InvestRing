/**
 * 五维正交维度（issue #128 / #135）的共享 UI 常量。
 * 维度字典数据来自 GET /api/asset-classifications，此处放展示标签与
 * 二级分组维度（issue #144）的共享事实来源。
 */

import type { AssetClassificationItem } from "@/types/asset-classification";

/** 可规则化的四个维度（asset_class 自身不参与规则/适用关联） */
export const RULE_DIMENSIONS = ["region", "style", "size", "segment"] as const;

export type RuleDimension = (typeof RULE_DIMENSIONS)[number];

/** 维度筛选键：asset_class + 可规则化四维（产品五维筛选的全集） */
export type DimensionFilterKey = "asset_class" | RuleDimension;

/** 维度筛选集：缺键 / 显式 undefined 均为「未筛选」（undefined 供联动清空写入） */
export type DimensionFilters = Partial<Record<DimensionFilterKey, string>>;

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

/**
 * 维度筛选下拉选项（issue #238 抽取，产品筛选弹窗与产品管理页共用）：
 * 启用值；选了 asset_class 则按 applicable_asset_classes 收窄。
 * dimension 含 "asset_class"：asset_class 维度值的 applicable_asset_classes 恒为空数组，
 * 但不参与收窄谓词（selectedAssetClass 未传时不判该项），故
 * getDimensionOptions(dictItems, "asset_class") 即「启用大类列表」的统一入口。
 */
export function getDimensionOptions(
  dictItems: AssetClassificationItem[],
  dimension: DimensionFilterKey,
  selectedAssetClass?: string
): AssetClassificationItem[] {
  return dictItems.filter(
    (i) =>
      i.dimension === dimension &&
      i.is_active &&
      (!selectedAssetClass || i.applicable_asset_classes.includes(selectedAssetClass))
  );
}

/**
 * 切换大类后的维度筛选集（issue #238 抽取）：返回新筛选集，
 * 不再适用新大类的维度值清空（避免查不出数据的隐形条件）；未选大类时仅更新 asset_class。
 */
export function clearInapplicableDims(
  dimFilters: DimensionFilters,
  newAssetClass: string | undefined,
  dictItems: AssetClassificationItem[]
): DimensionFilters {
  const next: DimensionFilters = { ...dimFilters, asset_class: newAssetClass };
  if (newAssetClass) {
    for (const dimension of RULE_DIMENSIONS) {
      const current = next[dimension];
      if (
        current &&
        !dictItems.some(
          (i) =>
            i.code === current &&
            i.is_active &&
            i.applicable_asset_classes.includes(newAssetClass)
        )
      ) {
        next[dimension] = undefined;
      }
    }
  }
  return next;
}
