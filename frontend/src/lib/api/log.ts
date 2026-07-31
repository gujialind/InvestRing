import { request } from "./client";
import { LoginLog, AuditLog, ErrorLog } from "@/types/log";

// 日志查询通用分页参数
interface LogQueryParams {
  page?: number;
  page_size?: number;
}

// 日志列表后端统一返回带 total 的分页结构
interface LogListResponse<T> {
  items: T[];
  total: number;
  page?: number;
  page_size?: number;
}

function unwrap<T>(res: LogListResponse<T> | T[]): T[] {
  return Array.isArray(res) ? res : res.items;
}

export const logApi = {
  loginLogs: (params?: LogQueryParams) =>
    request<LogListResponse<LoginLog> | LoginLog[]>({ method: "GET", url: "/system/logs/login", params }).then(unwrap),

  auditLogs: (params?: LogQueryParams) =>
    request<LogListResponse<AuditLog> | AuditLog[]>({ method: "GET", url: "/system/logs/audit", params }).then(unwrap),

  errorLogs: (params?: LogQueryParams) =>
    request<LogListResponse<ErrorLog> | ErrorLog[]>({ method: "GET", url: "/system/logs/error", params }).then(unwrap),

  // 任务执行历史请用 taskApi.executionHistory（GET /system/tasks/executions），
  // 后端不存在 /system/logs/task 端点
};
