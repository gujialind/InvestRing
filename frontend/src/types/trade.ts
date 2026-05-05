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
  notes?: string;
  created_at?: string;
  updated_at?: string;
}

export interface TradeCreate {
  portfolio_code: string;
  product_code: string;
  market?: string;
  platform_code?: string;
  trade_type: string;
  shares?: number;
  amount?: number;
  price?: number;
  fee?: number;
  actual_amount?: number;
  trade_date: string;
  notes?: string;
}

export interface TradeUpdate {
  shares?: number;
  amount?: number;
  price?: number;
  fee?: number;
  actual_amount?: number;
  confirm_date?: string;
  status?: string;
  notes?: string;
}
