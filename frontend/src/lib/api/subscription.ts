import { request } from "./client";
import {
  Subscription,
  SubscriptionCreate,
  SubscriptionUpdate,
} from "@/types/subscription";
import { PaginatedResponse } from "@/types/common";

export const subscriptionApi = {
  list: (params?: { page?: number; page_size?: number; portfolio_code?: string; status?: string }) =>
    request<PaginatedResponse<Subscription>>({ method: "GET", url: "/subscriptions", params }),

  get: (id: number) =>
    request<Subscription>({ method: "GET", url: `/subscriptions/${id}` }),

  create: (data: SubscriptionCreate) =>
    request<Subscription>({ method: "POST", url: "/subscriptions", data }),

  update: (id: number, data: SubscriptionUpdate) =>
    request<Subscription>({ method: "PUT", url: `/subscriptions/${id}`, data }),

  delete: (id: number) =>
    request<void>({ method: "DELETE", url: `/subscriptions/${id}` }),

  confirm: (id: number, data?: { confirm_date?: string; unit_price?: number }) =>
    request<Subscription>({ method: "POST", url: `/subscriptions/${id}/confirm`, data }),

  cancel: (id: number) =>
    request<Subscription>({ method: "POST", url: `/subscriptions/${id}/cancel` }),

  unconfirm: (id: number) =>
    request<void>({ method: "POST", url: `/subscriptions/${id}/unconfirm` }),
};
