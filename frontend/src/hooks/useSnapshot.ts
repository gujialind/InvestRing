import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { snapshotApi, getErrorMessage } from "@/lib/api";
import { useUIStore } from "@/stores/uiStore";

const SNAPSHOT_QUERY_KEY = "snapshots";

// 查询组合快照状态
export function useSnapshotStatus(portfolioCode: string) {
  return useQuery({
    queryKey: [SNAPSHOT_QUERY_KEY, "status", portfolioCode],
    queryFn: () => snapshotApi.getStatus(portfolioCode),
    enabled: !!portfolioCode,
  });
}

// 单日生成快照
export function useGenerateSnapshot() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: ({ portfolioCode, targetDate }: { portfolioCode: string; targetDate: string }) =>
      snapshotApi.generate(portfolioCode, targetDate),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [SNAPSHOT_QUERY_KEY] });
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      addToast({
        type: "success",
        title: "快照生成成功",
        message: `${data.portfolio_code} ${data.snapshot_date} 净值: ${data.unit_price?.toFixed(4)}`,
      });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "快照生成失败",
        message: getErrorMessage(error, "请检查依赖数据是否完整"),
      });
    },
  });
}

// 区间重算快照
export function useRecalculateSnapshots() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: ({
      portfolioCode,
      startDate,
      endDate,
      force,
    }: {
      portfolioCode: string | null;
      startDate: string;
      endDate: string;
      force?: boolean;
    }) => snapshotApi.recalculate(portfolioCode, startDate, endDate, force),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [SNAPSHOT_QUERY_KEY] });
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      
      const totalProcessed = data.results.reduce((sum, r) => sum + r.total_processed, 0);
      const totalErrors = data.results.reduce((sum, r) => sum + r.errors.length, 0);
      
      if (totalErrors === 0) {
        addToast({
          type: "success",
          title: "快照重算成功",
          message: `共处理 ${totalProcessed} 个交易日`,
        });
      } else {
        addToast({
          type: "warning",
          title: "快照重算完成（部分失败）",
          message: `成功 ${totalProcessed} 天，失败 ${totalErrors} 天`,
        });
      }
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "快照重算失败",
        message: getErrorMessage(error, "请稍后重试"),
      });
    },
  });
}

// 预检验证
export function useValidateSnapshot() {
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: ({ portfolioCode, targetDate }: { portfolioCode: string; targetDate: string }) =>
      snapshotApi.validate(portfolioCode, targetDate),
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "预检验证失败",
        message: getErrorMessage(error, "请稍后重试"),
      });
    },
  });
}

// 删除快照
export function useDeleteSnapshot() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: ({ portfolioCode, snapshotDate }: { portfolioCode: string; snapshotDate: string }) =>
      snapshotApi.delete(portfolioCode, snapshotDate),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [SNAPSHOT_QUERY_KEY] });
      addToast({
        type: "success",
        title: "删除成功",
        message: data.message,
      });
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "删除失败",
        message: getErrorMessage(error, "请稍后重试"),
      });
    },
  });
}
