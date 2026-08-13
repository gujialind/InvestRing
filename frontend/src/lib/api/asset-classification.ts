import { request } from "./client";
import {
  AssetClassificationCreate,
  AssetClassificationDetail,
  AssetClassificationListResponse,
  AssetClassificationUpdate,
} from "@/types/asset-classification";

export const assetClassificationApi = {
  /** 维度值字典（asset_class 的 sort_order 驱动饼图颜色/顺序与分区排序；
   *  顶层 dimension_rules 驱动产品表单必填/禁用与管理页矩阵） */
  list: (params?: { dimension?: string }) =>
    request<AssetClassificationListResponse>({
      method: "GET",
      url: "/asset-classifications",
      params,
    }),

  /** 单条详情（管理页编辑回填；asset_class 维度值附 dimension_rules） */
  get: (code: string) =>
    request<AssetClassificationDetail>({
      method: "GET",
      url: `/asset-classifications/${code}`,
    }),

  /** 新建维度值（管理面，issue #135；无删除端点，后悔药走 is_active） */
  create: (data: AssetClassificationCreate) =>
    request<AssetClassificationDetail>({
      method: "POST",
      url: "/asset-classifications",
      data,
    }),

  /** 更新维度值（code/dimension 不可改；关联与规则为全量替换语义） */
  update: (code: string, data: AssetClassificationUpdate) =>
    request<AssetClassificationDetail>({
      method: "PUT",
      url: `/asset-classifications/${code}`,
      data,
    }),
};
