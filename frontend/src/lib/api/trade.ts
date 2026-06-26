import { request } from "./client";
import { Trade, TradeCreate, TradeUpdate } from "@/types/trade";
import { PaginatedResponse } from "@/types/common";

export const tradeApi = {
  list: (params?: { page?: number; page_size?: number; portfolio_code?: string; status?: string }) =>
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
