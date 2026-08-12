import { request } from "./client";
import { AssetClassificationItem } from "@/types/asset-classification";

export const assetClassificationApi = {
  /** 维度值字典（issue #128 只读；asset_class 的 sort_order 驱动饼图颜色/顺序与分区排序） */
  list: (params?: { dimension?: string }) =>
    request<{ items: AssetClassificationItem[]; total: number }>({
      method: "GET",
      url: "/asset-classifications",
      params,
    }),
};
