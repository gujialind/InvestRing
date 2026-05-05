export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ApiErrorDetail {
  error: string;
  message: string;
}

export interface ApiError {
  detail: ApiErrorDetail;
}

export type Role = "admin" | "viewer";
export type PortfolioStatus = "draft" | "active" | "closed";
export type ProductType = "ETF" | "OEF" | "LOF" | "CASH";
export type TradeType = "buy" | "sell";
export type SubscriptionType = "subscribe" | "redeem";
export type TransactionStatus = "pending" | "confirmed" | "cancelled";
export type EventType =
  | "cash_dividend"
  | "reinvest_dividend"
  | "share_split"
  | "share_merge"
  | "bonus_share"
  | "forced_adjustment";
