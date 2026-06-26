import { request } from "./client";
import {
  SnapshotGenerationResult,
  RecalculationResult,
  SnapshotValidationResult,
  SnapshotStatusResponse,
} from "@/types/snapshot";

export const snapshotApi = {
  // 单日生成
  generate: (portfolioCode: string, targetDate: string) =>
    request<SnapshotGenerationResult>({
      method: "POST",
      url: "/v1/snapshots/generate",
      data: { portfolio_code: portfolioCode, target_date: targetDate },
    }),

  // 区间重算
  recalculate: (
    portfolioCode: string | null,
    startDate: string,
    endDate: string,
    force: boolean = false
  ) =>
    request<RecalculationResult>({
      method: "POST",
      url: "/v1/snapshots/recalculate",
      data: {
        portfolio_code: portfolioCode,
        start_date: startDate,
        end_date: endDate,
        force,
      },
    }),

  // 预检验证
  validate: (portfolioCode: string, targetDate: string) =>
    request<SnapshotValidationResult>({
      method: "GET",
      url: "/v1/snapshots/validation",
      params: { portfolio_code: portfolioCode, target_date: targetDate },
    }),

  // 查询状态
  getStatus: (portfolioCode: string) =>
    request<SnapshotStatusResponse>({
      method: "GET",
      url: `/v1/snapshots/portfolios/${portfolioCode}/status`,
    }),

  // 删除快照
  delete: (portfolioCode: string, snapshotDate: string) =>
    request<{ success: boolean; message: string }>({
      method: "DELETE",
      url: `/v1/snapshots/${portfolioCode}/${snapshotDate}`,
    }),
};
