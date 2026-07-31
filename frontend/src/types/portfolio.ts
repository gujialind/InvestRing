export interface Portfolio {
  code: string;
  name: string;
  description?: string;
  status: string;
  started_at?: string;
  closed_at?: string;
  created_at?: string;
  updated_at?: string;
  // 以下字段由后端在列表接口中动态计算返回
  total_value?: number;
  cumulative_return?: number;
  investor_count?: number;
}

export interface PortfolioCreate {
  code: string;
  name: string;
  description?: string;
}

export interface PortfolioUpdate {
  name?: string;
  description?: string;
}

export interface PortfolioValueSnapshot {
  id: number;
  portfolio_code: string;
  total_value: number;
  total_shares: number;
  unit_price: number;
  snapshot_date: string;
  created_at?: string;
}

// GET /portfolios/{code}/nav-history 返回项
export interface NavHistoryRecord {
  snapshot_date: string;
  unit_price: number | null;
  total_value: number | null;
  total_shares: number | null;
}

// GET /portfolios/{code}/returns 返回（快照不足时字段为 null）
export interface PortfolioReturns {
  portfolio_code: string;
  cumulative_return: number | null;
  annualized_return: number | null;
  initial_nav: number | null;
  current_nav: number | null;
  holding_days: number | null;
}
