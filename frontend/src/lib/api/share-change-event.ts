import { request } from "./client";
import {
  ShareChangeEvent,
  ShareChangeEventCreate,
  ShareChangeEventUpdate,
} from "@/types/share-change-event";
import { PaginatedResponse } from "@/types/common";

export const shareChangeEventApi = {
  list: (params?: { page?: number; page_size?: number; portfolio_code?: string }) =>
    request<PaginatedResponse<ShareChangeEvent>>({
      method: "GET",
      url: "/share-change-events",
      params,
    }),

  get: (id: number) =>
    request<ShareChangeEvent>({ method: "GET", url: `/share-change-events/${id}` }),

  create: (data: ShareChangeEventCreate) =>
    request<ShareChangeEvent>({ method: "POST", url: "/share-change-events", data }),

  update: (id: number, data: ShareChangeEventUpdate) =>
    request<ShareChangeEvent>({ method: "PUT", url: `/share-change-events/${id}`, data }),

  confirm: (id: number) =>
    request<{ message: string; event: ShareChangeEvent }>({
      method: "POST",
      url: `/share-change-events/${id}/confirm`,
    }),

  cancel: (id: number) =>
    request<{ message: string }>({
      method: "POST",
      url: `/share-change-events/${id}/cancel`,
    }),

  delete: (id: number) =>
    request<{ message: string }>({
      method: "DELETE",
      url: `/share-change-events/${id}`,
    }),
};
