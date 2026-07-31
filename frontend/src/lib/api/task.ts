import { request } from "./client";
import { PaginatedResponse } from "@/types/common";
import { ScheduledTask, TaskExecution } from "@/types/log";

export const taskApi = {
  // 后端返回分页对象 {items, total, page, page_size}
  list: (params?: { page?: number; page_size?: number }) =>
    request<PaginatedResponse<ScheduledTask>>({ method: "GET", url: "/system/tasks", params }),

  run: (code: string) =>
    request<{ message: string }>({ method: "POST", url: `/system/tasks/${code}/run` }),

  enable: (code: string) =>
    request<{ message: string }>({ method: "POST", url: `/system/tasks/${code}/enable` }),

  disable: (code: string) =>
    request<{ message: string }>({ method: "POST", url: `/system/tasks/${code}/disable` }),

  // 全局执行历史（跨任务，可选按 task_code 过滤）
  executionHistory: (params?: { task_code?: string; page?: number; page_size?: number }) =>
    request<PaginatedResponse<TaskExecution>>({ method: "GET", url: "/system/tasks/executions", params }),
};
