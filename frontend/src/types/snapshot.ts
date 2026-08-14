export interface SnapshotValidationCheck {
  check_type: string;
  status: "passed" | "failed" | "warning";
  message: string;
}

export interface SnapshotValidationResult {
  portfolio_code: string;
  target_date: string;
  is_valid: boolean;
  checks: SnapshotValidationCheck[];
}

// 后端非阻断告警（issue #71：如负现金）
export type SnapshotWarning = Record<string, unknown>;

export interface SnapshotGenerationResult {
  success: boolean;
  message: string;
  portfolio_code: string;
  snapshot_date: string;
  total_value?: number;
  total_shares?: number;
  unit_price?: number;
  warnings?: SnapshotWarning[] | null;
}

export interface RecalculationPortfolioResult {
  portfolio_code: string;
  processed_dates: string[];
  total_processed: number;
  errors: Array<{ date: string; error: string }>;
  warnings?: SnapshotWarning[] | null;
}

export interface RecalculationResult {
  success: boolean;
  message: string;
  results: RecalculationPortfolioResult[];
}

export interface SnapshotStatusResponse {
  portfolio_code: string;
  latest_snapshot_date?: string;
  total_snapshots: number;
  first_snapshot_date?: string;
  missing_dates: string[];
  /** 最新快照日 CASH 持仓 cash_amount < 0 的平台清单（正常为空） */
  negative_cash_platforms?: string[];
  /** 组合级自动快照开关（issue #156），随组合配置返回 */
  auto_snapshot_enabled: boolean;
}

// ---- #146 快照管理页重构 ----

export interface SnapshotListItem {
  snapshot_date: string;
  unit_price: number;
  total_shares: number;
  total_value: number;
  in_transit_total: number;
}

export interface SnapshotListResponse {
  portfolio_code: string;
  items: SnapshotListItem[];
  /** 过滤后全量计数（limit 截断前），total > items.length 即被截断 */
  total: number;
  limit: number;
}

export interface SnapshotCatchUpResult {
  portfolio_code: string;
  to_date: string;
  generated_count: number;
  generated_dates: string[];
  latest_snapshot_date?: string | null;
  message?: string | null;
  failed_date?: string | null;
  error?: string | null;
}

export interface SnapshotGenerateNextResult {
  success: boolean;
  message: string;
  portfolio_code: string;
  generated_date: string;
  total_value?: number;
  total_shares?: number;
  unit_price?: number;
  warnings?: SnapshotWarning[] | null;
}

export interface RecalculateAsyncSubmitResult {
  job_id: number;
  status: string;
  message: string;
}

export interface BulkDeleteDryRunResult {
  dry_run: true;
  portfolio_code: string;
  from_date: string;
  count: number;
  /** 将删除的快照日期（倒序） */
  snapshot_dates: string[];
}

export interface BulkDeleteResult {
  success: boolean;
  message: string;
  deleted_count: number;
  details?: Array<{
    snapshot_date: string;
    deleted: number;
    cascaded_subs: number;
    cascaded_events: number;
  }>;
}
