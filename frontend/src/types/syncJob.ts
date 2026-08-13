// 后台同步任务（对齐后端 SyncJobResponse，GET /api/sync-jobs/{id}）
export interface SyncJob {
  id: number;
  job_type: string;
  /** pending | running | success | failed */
  status: string;
  params?: Record<string, unknown> | null;
  total: number;
  done: number;
  success_count: number;
  failed_count: number;
  skipped_count: number;
  error_message?: string | null;
  triggered_by: string;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}
