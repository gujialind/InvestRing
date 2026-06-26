import { request } from "./client";
import { NotificationItem } from "@/types/notification";
import { PaginatedResponse } from "@/types/common";

export const notificationApi = {
  list: (params?: { page?: number; page_size?: number; status?: string }) =>
    request<PaginatedResponse<NotificationItem>>({ method: "GET", url: "/system/notifications", params }),

  markAsRead: (id: number) =>
    request<{ message: string }>({ method: "POST", url: `/system/notifications/${id}/read` }),

  markAllAsRead: () =>
    request<{ message: string }>({ method: "POST", url: "/system/notifications/read-all" }),
};
