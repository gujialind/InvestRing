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
}
