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

export interface SnapshotGenerationResult {
  success: boolean;
  message: string;
  portfolio_code: string;
  snapshot_date: string;
  total_value?: number;
  total_shares?: number;
  unit_price?: number;
}

export interface RecalculationPortfolioResult {
  portfolio_code: string;
  processed_dates: string[];
  total_processed: number;
  errors: Array<{ date: string; error: string }>;
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
}
