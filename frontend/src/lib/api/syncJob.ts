import { request } from "./client";
import { SyncJob } from "@/types/syncJob";

export const syncJobApi = {
  // 查询后台任务状态（#146 重算进度轮询）
  get: (jobId: number) =>
    request<SyncJob>({
      method: "GET",
      url: `/sync-jobs/${jobId}`,
    }),
};
