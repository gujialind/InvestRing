"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { productApi, getErrorMessage } from "@/lib/api";
import { ProductCreate, ProductUpdate } from "@/types/product";
import { useUIStore } from "@/stores/uiStore";

const PRODUCT_QUERY_KEY = "products";

// 产品列表 Hook
export function useProductList(params?: { page?: number; page_size?: number; product_type?: string }) {
  return useQuery({
    queryKey: [PRODUCT_QUERY_KEY, "list", params],
    queryFn: () => productApi.list(params),
    staleTime: 30 * 1000,
  });
}

// 单个产品详情 Hook
export function useProduct(code: string, market?: string) {
  return useQuery({
    queryKey: [PRODUCT_QUERY_KEY, code, market],
    queryFn: () => productApi.get(code, market),
    enabled: !!code,
    staleTime: 30 * 1000,
  });
}

// 创建产品 Hook
export function useCreateProduct() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (data: ProductCreate) => productApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PRODUCT_QUERY_KEY, "list"] });
      addToast({
        type: "success",
        title: "创建成功",
        message: "产品已创建",
      });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "创建失败",
        message: getErrorMessage(error, "请检查输入信息"),
      });
    },
  });
}

// 更新产品 Hook
export function useUpdateProduct(code: string, market?: string) {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (data: ProductUpdate) => productApi.update(code, data, market),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PRODUCT_QUERY_KEY, code] });
      queryClient.invalidateQueries({ queryKey: [PRODUCT_QUERY_KEY, "list"] });
      addToast({
        type: "success",
        title: "更新成功",
        message: "产品信息已更新",
      });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "更新失败",
        message: getErrorMessage(error, "请稍后重试"),
      });
    },
  });
}

// 删除产品 Hook
export function useDeleteProduct() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: ({ code, market }: { code: string; market?: string }) => productApi.delete(code, market),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PRODUCT_QUERY_KEY, "list"] });
      addToast({
        type: "success",
        title: "删除成功",
        message: "产品已删除",
      });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "删除失败",
        message: getErrorMessage(error, "该产品已被使用，无法删除"),
      });
    },
  });
}
