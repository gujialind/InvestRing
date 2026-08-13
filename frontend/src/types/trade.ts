export interface Trade {
  id: number;
  portfolio_code: string;
  product_code: string;
  market?: string;
  platform_code?: string;
  trade_type: string;
  shares?: number;
  amount?: number;
  price?: number;
  fee: number;
  actual_amount?: number;
  trade_date: string;
  confirm_date?: string;
  status: string;
  /** 业务分组（#126 决策⑨）：rebal_*=调仓配对、sub_*=申赎现金腿、12位hex=现金转移；仅用于结对展示，页面不展示该编码 */
  transfer_group?: string;
  notes?: string;
  created_at?: string;
  updated_at?: string;
}

export interface TradeCreate {
  portfolio_code: string;
  product_code: string;
  market?: string;
  platform_code?: string;
  // 跨平台现金腿（#91）：买=扣款平台、卖=到账平台，缺省同基金腿平台
  cash_platform_code?: string;
  trade_type: string;
  shares?: number;
  amount?: number;
  price?: number;
  fee?: number;
  actual_amount?: number;
  trade_date: string;
  notes?: string;
  /** 命中 DUPLICATE_TRADE 时用户确认后重试传 true（后端默认 false） */
  allow_duplicate?: boolean;
}

// 字段与后端 schemas/trade.py::TradeUpdate 对齐：
// 不含 confirm_date/status（后端会静默丢弃）；改状态请走 confirm/unconfirm/cancel 端点
export interface TradeUpdate {
  shares?: number;
  amount?: number;
  price?: number;
  fee?: number;
  actual_amount?: number;
  trade_date?: string;
  notes?: string;
}
