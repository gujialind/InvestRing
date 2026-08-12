/**
 * 资产分类维度字典（issue #128 只读字典；#135 管理面 + 适用关系双层落库）。
 * asset_class 维度的 sort_order 即前端色板序位（变更即改色，见 lib/colors.ts）。
 */

/** 维度级规则取值；无规则行 = forbidden（不出现键） */
export type DimensionRule = "required" | "optional";

/** 维度值字典项（GET /api/asset-classifications 返回） */
export interface AssetClassificationItem {
  code: string;
  /** 维度：asset_class / region / style / size / segment */
  dimension: string;
  name: string;
  sort_order: number;
  description?: string | null;
  /** 软失效开关：false = 停用（存量引用不阻断，新建/变更引用被拒） */
  is_active: boolean;
  /** 值级适用 asset_class（asset_class 维度值恒为空数组），按大类色板序位排序 */
  applicable_asset_classes: string[];
}

/** 单条详情：asset_class 维度值附 dimension_rules（其余维度恒空对象） */
export interface AssetClassificationDetail extends AssetClassificationItem {
  /** {dimension: rule}，未出现的维度 = forbidden */
  dimension_rules: Record<string, DimensionRule>;
}

/** 字典全量响应；dimension_rules 为维度级适用矩阵 {asset_class: {dimension: rule}} */
export interface AssetClassificationListResponse {
  items: AssetClassificationItem[];
  dimension_rules: Record<string, Record<string, DimensionRule>>;
  total: number;
}

/** 新建维度值。code 前缀须与 dimension 匹配（ASSET_/REGION_/STYLE_/SIZE_/SEG_，
 * 全大写）；非 asset_class 维度必须 ≥1 适用大类；dimension_rules 仅 asset_class
 * 可携带（缺省 = 现金型全 forbidden） */
export interface AssetClassificationCreate {
  code: string;
  dimension: string;
  name: string;
  sort_order?: number;
  description?: string | null;
  applicable_asset_classes?: string[];
  dimension_rules?: Record<string, DimensionRule>;
}

/** 更新维度值（code/dimension 不可改，故不在此类型中）。
 * applicable_asset_classes / dimension_rules 为全量替换语义（不传 = 不动）。 */
export interface AssetClassificationUpdate {
  name?: string;
  sort_order?: number;
  description?: string | null;
  is_active?: boolean;
  applicable_asset_classes?: string[];
  dimension_rules?: Record<string, DimensionRule>;
}
