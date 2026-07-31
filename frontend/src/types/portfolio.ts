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

// GET /portfolios/{code}/returns 返回（轻量口径：累计 + 年化）
export interface PortfolioReturns {
  portfolio_code: string;
  cumulative_return: number | null;
  annualized_return: number | null;
  initial_nav: number | null;
  current_nav: number | null;
  holding_days: number | null;
}

/**
 * GET /portfolios/{code}/performance 返回（全量绩效与风险指标）
 *
 * twr：时间加权收益率，消除资金进出影响（本系统为净值化记账，等于净值增长率）
 * mwr：资金加权收益率（XIRR），反映实际投入资金的年化回报
 * twr > mwr 通常说明大部分资金买在高位（加仓时点不佳）
 */
export interface PortfolioPerformance {
  portfolio_code: string;
  twr: number | null;
  twr_chained: number | null;
  annualized_twr: number | null;
  mwr: number | null;
  initial_nav: number | null;
  current_nav: number | null;
  holding_days: number | null;
  return_1m: number | null;
  return_3m: number | null;
  return_ytd: number | null;
  max_drawdown: number | null;
  max_drawdown_peak_date: string | null;
  max_drawdown_trough_date: string | null;
  annualized_volatility: number | null;
  cash_flow_count: number;
  /** 两种 TWR 算法一致性自检：false 说明净值序列异常 */
  nav_series_consistent: boolean | null;
  /** 持有期 < 90 天时为 false：年化（尤其 MWR）属大幅外推，仅供参考 */
  annualization_reliable: boolean;
}
