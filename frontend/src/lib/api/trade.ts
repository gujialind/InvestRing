import { request } from "./client";
import { Trade, TradeCreate, TradeUpdate } from "@/types/trade";
import { PaginatedResponse } from "@/types/common";

/**
 * 调仓列表查询参数（#126 服务端筛选）。
 * axios 会丢弃 undefined 值，空筛选自然不传参。
 */
export interface TradeListParams {
  page?: number;
  page_size?: number;
  portfolio_code?: string;
  status?: string;
  trade_type?: string;
  product_code?: string;
  market?: string;
  /**
   * 多选产品过滤（issue #155）：逗号分隔的 `code|market` 复合值（market 段可空，如 `CASH|`）。
   * 与 product_code/market 单值参数互斥，同传后端返回 422。
   */
  products?: string;
  platform_code?: string;
  trade_date_start?: string;
  trade_date_end?: string;
  confirm_date_start?: string;
  confirm_date_end?: string;
}

export const tradeApi = {
  list: (params?: TradeListParams) =>
    request<PaginatedResponse<Trade>>({ method: "GET", url: "/trades", params }),

  get: (id: number) =>
    request<Trade>({ method: "GET", url: `/trades/${id}` }),

  create: (data: TradeCreate) =>
    request<Trade>({ method: "POST", url: "/trades", data }),

  update: (id: number, data: TradeUpdate) =>
    request<Trade>({ method: "PUT", url: `/trades/${id}`, data }),

  delete: (id: number) =>
    request<void>({ method: "DELETE", url: `/trades/${id}` }),

  confirm: (id: number, data?: { confirm_date?: string; price?: number }) =>
    request<Trade>({ method: "POST", url: `/trades/${id}/confirm`, data }),

  cancel: (id: number) =>
    request<Trade>({ method: "POST", url: `/trades/${id}/cancel` }),

  unconfirm: (id: number) =>
    request<void>({ method: "POST", url: `/trades/${id}/unconfirm` }),

  batchRebalance: (portfolioCode: string, trades: TradeCreate[], idempotencyKey?: string) =>
    request<{ created_trades: Trade[] }>({
      method: "POST",
      url: `/portfolios/${portfolioCode}/batch-rebalance`,
      data: { trades },
      headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined,
    }),
};
