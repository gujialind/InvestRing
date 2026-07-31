export interface Position {
  id: number;
  portfolio_code: string;
  product_code: string;
  product_name?: string;
  market?: string;
  platform_code?: string;
  shares?: number;
  frozen_shares?: number;
  cost_price?: number;
  unit_price?: number;
  market_value?: number;
  cash_amount?: number;
  frozen_amount?: number;
  asset_type?: string;
  profit_loss?: number;
  profit_loss_percent?: number;
  snapshot_date: string;
  created_at?: string;
}

export interface PositionCreate {
  portfolio_code: string;
  product_code: string;
  market?: string;
  platform_code?: string;
  shares?: number;
  frozen_shares?: number;
  cost_price?: number;
  unit_price?: number;
  market_value?: number;
  cash_amount?: number;
  frozen_amount?: number;
  snapshot_date: string;
}

export interface PositionUpdate {
  platform_code?: string;
  shares?: number;
  frozen_shares?: number;
  cost_price?: number;
  unit_price?: number;
  market_value?: number;
  cash_amount?: number;
  frozen_amount?: number;
  snapshot_date?: string;
}
