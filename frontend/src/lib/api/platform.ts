import { request } from "./client";
import { Platform, PlatformCreate, PlatformUpdate } from "@/types/platform";
import { PaginatedResponse } from "@/types/common";

export const platformApi = {
  list: (params?: { page?: number; page_size?: number }) =>
    request<PaginatedResponse<Platform>>({ method: "GET", url: "/platforms", params }),

  get: (code: string) =>
    request<Platform>({ method: "GET", url: `/platforms/${code}` }),

  create: (data: PlatformCreate) =>
    request<Platform>({ method: "POST", url: "/platforms", data }),

  update: (code: string, data: PlatformUpdate) =>
    request<Platform>({ method: "PUT", url: `/platforms/${code}`, data }),

  delete: (code: string) =>
    request<{ message: string }>({ method: "DELETE", url: `/platforms/${code}` }),
};
