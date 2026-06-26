import { request } from "./client";
import { ScheduledTask, TaskExecution } from "@/types/log";

export const taskApi = {
  list: () =>
    request<ScheduledTask[]>({ method: "GET", url: "/system/tasks" }),

  run: (code: string) =>
    request<{ message: string }>({ method: "POST", url: `/system/tasks/${code}/run` }),

  enable: (code: string) =>
    request<{ message: string }>({ method: "POST", url: `/system/tasks/${code}/enable` }),

  disable: (code: string) =>
    request<{ message: string }>({ method: "POST", url: `/system/tasks/${code}/disable` }),

  executionHistory: (params?: { task_code?: string; page?: number; page_size?: number }) =>
    request<TaskExecution[]>({ method: "GET", url: "/system/tasks/executions", params }),
};
