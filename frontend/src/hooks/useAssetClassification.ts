"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  assetClassificationApi,
  getErrorMessage,
  AssetClassificationCreate,
  AssetClassificationUpdate,
} from "@/lib/api";
import { useUIStore } from "@/stores/uiStore";

const AC_QUERY_KEY = "asset-classifications";

/**
 * 维度字典 Hook（issue #128）：字典近乎静态，staleTime 拉长到 5 分钟。
 * 传 dimension 按维度过滤（饼图/分区只需 "asset_class"），缺省取全量。
 */
export function useAssetClassifications(dimension?: string) {
  return useQuery({
    queryKey: [AC_QUERY_KEY, dimension ?? "all"],
    queryFn: () =>
      assetClassificationApi.list(dimension ? { dimension } : undefined),
    staleTime: 5 * 60 * 1000,
  });
}

/** 单条详情 Hook（管理页编辑回填用，issue #135） */
export function useAssetClassification(code: string) {
  return useQuery({
    queryKey: [AC_QUERY_KEY, "detail", code],
    queryFn: () => assetClassificationApi.get(code),
    enabled: !!code,
    staleTime: 5 * 60 * 1000,
  });
}

/** 新建维度值（issue #135） */
export function useCreateAssetClassification() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (data: AssetClassificationCreate) =>
      assetClassificationApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [AC_QUERY_KEY] });
      addToast({ type: "success", title: "创建成功", message: "维度值已创建" });
    },
    onError: (error: unknown) => {
      addToast({ type: "error", title: "创建失败", message: getErrorMessage(error, "请检查输入信息") });
    },
  });
}

/** 更新维度值（code 随 mutate 传入；关联/规则为全量替换语义） */
export function useUpdateAssetClassification() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: ({ code, data }: { code: string; data: AssetClassificationUpdate }) =>
      assetClassificationApi.update(code, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [AC_QUERY_KEY] });
      addToast({ type: "success", title: "更新成功", message: "维度值已更新" });
    },
    onError: (error: unknown) => {
      addToast({ type: "error", title: "更新失败", message: getErrorMessage(error, "请稍后重试") });
    },
  });
}
