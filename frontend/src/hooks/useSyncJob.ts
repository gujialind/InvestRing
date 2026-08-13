import { useQuery } from "@tanstack/react-query";
import { syncJobApi } from "@/lib/api";

/**
 * 后台任务状态轮询（#146 重算进度）。
 * 函数式 refetchInterval（react-query v5）：仅 pending/running 每 2s 轮询，
 * 终态（success/failed）或无数据即停，避免终态后无限轮询。
 */
export function useSyncJob(jobId: number | null) {
  return useQuery({
    queryKey: ["sync-jobs", jobId],
    queryFn: () => syncJobApi.get(jobId!),
    enabled: jobId != null,
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === "pending" || s === "running" ? 2000 : false;
    },
  });
}
