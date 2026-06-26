"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { positionApi, getErrorMessage } from "@/lib/api";
import { PositionCreate, PositionUpdate } from "@/types/position";
import { useUIStore } from "@/stores/uiStore";

const POSITION_QUERY_KEY = "positions";

export function usePositionList(
  portfolioCode: string,
  params?: { page?: number; page_size?: number; snapshot_date?: string }
) {
  return useQuery({
    queryKey: [POSITION_QUERY_KEY, portfolioCode, "list", params],
    queryFn: () => positionApi.list(portfolioCode, params),
    enabled: !!portfolioCode,
    staleTime: 30 * 1000,
  });
}

export function useLatestPositions(portfolioCode: string) {
  return useQuery({
    queryKey: [POSITION_QUERY_KEY, portfolioCode, "latest"],
    queryFn: () => positionApi.getLatest(portfolioCode),
    enabled: !!portfolioCode,
    staleTime: 30 * 1000,
  });
}

export function usePositionAttribution(portfolioCode: string) {
  return useQuery({
    queryKey: [POSITION_QUERY_KEY, portfolioCode, "attribution"],
    queryFn: () => positionApi.getAttribution(portfolioCode),
    enabled: !!portfolioCode,
    staleTime: 60 * 1000,
  });
}

export function useCreatePosition() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (data: PositionCreate) => positionApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [POSITION_QUERY_KEY] });
      addToast({
        type: "success",
        title: "创建成功",
        message: "持仓已创建",
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

export function useUpdatePosition() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: PositionUpdate }) =>
      positionApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [POSITION_QUERY_KEY] });
      addToast({
        type: "success",
        title: "更新成功",
        message: "持仓信息已更新",
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