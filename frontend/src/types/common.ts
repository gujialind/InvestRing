export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ApiErrorDetail {
  error: string;
  message: string;
  /** 后端 BusinessError 附带的结构化上下文（如 MARKET_AMBIGUOUS 的 available_markets） */
  details?: Record<string, unknown>;
}

export interface ApiError {
  /** 后端存在两种形态：结构化对象与裸字符串（HTTPException(detail="...")） */
  detail: ApiErrorDetail | string;
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
