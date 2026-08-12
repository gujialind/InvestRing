export interface Position {
  id: number;
  portfolio_code: string;
  product_code: string;
  product_name?: string;
  market?: string;
  platform_code?: string;
  platform_name?: string | null;
  shares?: number;
  frozen_shares?: number;
  cost_price?: number;
  unit_price?: number;
  market_value?: number;
  cash_amount?: number;
  frozen_amount?: number;
  profit_loss?: number;
  profit_loss_percent?: number;
  // 读侧派生（issue #128）：5 维度 code+name 成对输出；CASH 行仅 asset_class=现金、
  // 其余维度 NULL；IN_TRANSIT 在途行五维全 NULL
  asset_class_code?: string | null;
  asset_class_name?: string | null;
  region_code?: string | null;
  region_name?: string | null;
  style_code?: string | null;
  style_name?: string | null;
  size_code?: string | null;
  size_name?: string | null;
  segment_code?: string | null;
  segment_name?: string | null;
  // 读侧派生（issue #99）：daily_profit=当日收益（首个快照日 / IN_TRANSIT 在途行 → null）
  daily_profit?: number | null;
  /** QDII 按 T-1 净值估值，日收益滞后一天（前端 tooltip 提示） */
  is_qdii?: boolean | null;
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
