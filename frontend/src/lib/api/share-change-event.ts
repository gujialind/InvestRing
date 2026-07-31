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

  create: (data: ShareChangeEventCreate, options?: { forceCover?: boolean }) =>
    request<ShareChangeEvent>({
      method: "POST",
      url: "/share-change-events",
      data,
      // 平台级事件未覆盖全部持仓平台时，后端默认阻断（PLATFORM_NOT_COVERED）；
      // force_cover=true 降为 warning 强制提交
      params: options?.forceCover ? { force_cover: true } : undefined,
    }),

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
