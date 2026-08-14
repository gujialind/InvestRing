import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { snapshotApi, getErrorMessage } from "@/lib/api";
import { formatNav } from "@/lib/utils";
import { useUIStore } from "@/stores/uiStore";
import type { BulkDeleteDryRunResult, BulkDeleteResult } from "@/types/snapshot";

const SNAPSHOT_QUERY_KEY = "snapshots";

// 查询组合快照状态
export function useSnapshotStatus(portfolioCode: string) {
  return useQuery({
    queryKey: [SNAPSHOT_QUERY_KEY, "status", portfolioCode],
    queryFn: () => snapshotApi.getStatus(portfolioCode),
    enabled: !!portfolioCode,
  });
}

// 快照历史列表（#146；#152 日期区间筛选）：["snapshots"] 前缀失效即同时刷 status+list。
// 区间入 queryKey 防缓存碰撞；undefined 字段 axios 自然不传参（X 清空 = 不按日期过滤）
export function useSnapshotList(
  portfolioCode: string,
  range?: { startDate?: string; endDate?: string }
) {
  return useQuery({
    queryKey: [SNAPSHOT_QUERY_KEY, "list", portfolioCode, range?.startDate, range?.endDate],
    queryFn: () =>
      snapshotApi.list(portfolioCode, {
        start_date: range?.startDate,
        end_date: range?.endDate,
      }),
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
        message: `${data.portfolio_code} ${data.snapshot_date} 净值: ${formatNav(data.unit_price)}`,
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

// 生成下一交易日快照（#146 主操作，替代旧"快速更新"）
export function useGenerateNextSnapshot() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (portfolioCode: string) => snapshotApi.generateNext(portfolioCode),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [SNAPSHOT_QUERY_KEY] });
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      addToast({
        type: "success",
        title: "快照生成成功",
        message: `已生成 ${data.generated_date}，净值 ${formatNav(data.unit_price)}`,
      });
    },
    onError: (error: unknown) => {
      // NO_SNAPSHOT_BASELINE / CALENDAR_NOT_SYNCED 等 message 直接透传可见
      addToast({
        type: "error",
        title: "生成下一日快照失败",
        message: getErrorMessage(error, "请稍后重试"),
      });
    },
  });
}

// 逐交易日追平（#146）：逐日 checkpoint，单日失败前功保留
export function useCatchUpSnapshots() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: ({ portfolioCode, toDate }: { portfolioCode: string; toDate: string }) =>
      snapshotApi.catchUp(portfolioCode, toDate),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [SNAPSHOT_QUERY_KEY] });
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      if (data.failed_date) {
        addToast({
          type: "warning",
          title: "快照追平中断",
          message: `追平中断于 ${data.failed_date}，已生成 ${data.generated_count} 日：${data.error ?? "未知错误"}`,
        });
      } else {
        addToast({
          type: "success",
          title: "快照追平完成",
          message: data.message ?? `共生成 ${data.generated_count} 日快照`,
        });
      }
    },
    onError: (error: unknown) => {
      addToast({
        type: "error",
        title: "快照追平失败",
        message: getErrorMessage(error, "请稍后重试"),
      });
    },
  });
}

// 异步区间重算（#146）：只提交任务，终态 toast 由组件经 useSyncJob 轮询处理后触发
export function useRecalculateAsync() {
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: ({
      portfolioCode,
      startDate,
      endDate,
    }: {
      portfolioCode: string;
      startDate: string;
      endDate: string;
    }) => snapshotApi.recalculateAsync(portfolioCode, startDate, endDate),
    // onSuccess 不 toast 终态——由组件接 job_id 置 activeJobId，进度与终态在页面内展示
    onError: (error: unknown) => {
      // 409 RECALC_JOB_CONFLICT 的 message「已有快照重算任务在运行中」直接展示
      addToast({
        type: "error",
        title: "提交重算任务失败",
        message: getErrorMessage(error, "请稍后重试"),
      });
    },
  });
}

// 批量删除（#146 两段式）：dry_run 不 toast；confirm 成功 toast 由组件处理，hook 只负责失效
// variables 判别联合保证 api 泛型按 mode 收窄；组件经 "dry_run" in data 判别返回类型
type BulkDeleteVariables =
  | { portfolioCode: string; fromDate: string; mode: "dry_run" }
  | { portfolioCode: string; fromDate: string; mode: "confirm" };

export function useBulkDeleteSnapshots() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (vars: BulkDeleteVariables): Promise<BulkDeleteDryRunResult | BulkDeleteResult> =>
      vars.mode === "dry_run"
        ? snapshotApi.deleteBulk(vars.portfolioCode, vars.fromDate, "dry_run")
        : snapshotApi.deleteBulk(vars.portfolioCode, vars.fromDate, "confirm"),
    onSuccess: (_data, variables) => {
      if (variables.mode === "confirm") {
        queryClient.invalidateQueries({ queryKey: [SNAPSHOT_QUERY_KEY] });
        queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      }
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
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
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
