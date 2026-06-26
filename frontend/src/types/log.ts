export interface LoginLog {
  id: number;
  user_code?: string;
  investor_code?: string; // 后端历史字段
  ip?: string;
  ip_address?: string; // 后端历史字段
  user_agent?: string;
  success?: boolean;
  status?: string; // "success" | "failed"
  message?: string;
  created_at: string;
}

export interface AuditLog {
  id: number;
  action: string;
  details?: string;
  user_code?: string;
  investor_code?: string; // 后端历史字段
  resource_type?: string;
  resource_name?: string;
  ip?: string;
  created_at: string;
}

export interface ErrorLog {
  id: number;
  error_type?: string;
  message: string;
  error_message?: string; // 后端历史字段
  stack?: string;
  path?: string;
  user_code?: string;
  created_at: string;
}

export interface TaskLog {
  id: number;
  task_code: string;
  status: string; // "success" | "failed" | "running"
  started_at: string;
  finished_at?: string;
  duration_ms?: number;
  error_message?: string;
  created_at?: string;
}

export interface ScheduledTask {
  id: number;
  code: string;
  task_code?: string; // 后端历史字段别名
  name?: string;
  description?: string;
  cron?: string;
  cron_expression?: string; // 后端历史字段
  is_enabled: boolean;
  last_run_at?: string;
}

export interface TaskExecution {
  id: number;
  task_code: string;
  status: string;
  started_at: string;
  finished_at?: string;
  completed_at?: string; // 后端历史字段
  duration_ms?: number;
  error_message?: string;
}
