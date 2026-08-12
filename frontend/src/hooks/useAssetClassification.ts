"use client";

import { useQuery } from "@tanstack/react-query";
import { assetClassificationApi } from "@/lib/api";

/**
 * 维度字典 Hook（issue #128）：字典近乎静态，staleTime 拉长到 5 分钟。
 * 传 dimension 按维度过滤（饼图/分区只需 "asset_class"），缺省取全量。
 */
export function useAssetClassifications(dimension?: string) {
  return useQuery({
    queryKey: ["asset-classifications", dimension ?? "all"],
    queryFn: () =>
      assetClassificationApi.list(dimension ? { dimension } : undefined),
    staleTime: 5 * 60 * 1000,
  });
}
