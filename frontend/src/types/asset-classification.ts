/**
 * 资产分类维度字典项（issue #128，GET /api/asset-classifications 返回）。
 * asset_class 维度的 sort_order 即前端色板序位（变更即改色，见 lib/colors.ts）。
 */
export interface AssetClassificationItem {
  code: string;
  /** 维度：asset_class / region / style / size / segment */
  dimension: string;
  name: string;
  sort_order: number;
  description?: string | null;
}
