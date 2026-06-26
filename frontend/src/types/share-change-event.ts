import { EventType, TransactionStatus } from "./common";

export interface ShareChangeEvent {
  id: number;
  portfolio_code: string;
  event_type: EventType;
  event_date: string;
  entitlement_date: string;
  product_code?: string;
  market?: string;
  shares_before?: number;
  shares_change?: number;
  shares_after?: number;
  cash_change?: number;
  div_cash?: number;
  reinvest_nav?: number;
  ratio?: number;
  status: TransactionStatus;
  notes?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ShareChangeEventCreate {
  portfolio_code: string;
  event_type: EventType;
  event_date: string;
  entitlement_date: string;
  product_code?: string;
  market?: string;
  shares_before?: number;
  shares_change?: number;
  shares_after?: number;
  cash_change?: number;
  div_cash?: number;
  reinvest_nav?: number;
  ratio?: number;
  status?: string;
  notes?: string;
}

export interface ShareChangeEventUpdate {
  event_date?: string;
  entitlement_date?: string;
  shares_before?: number;
  shares_change?: number;
  shares_after?: number;
  cash_change?: number;
  div_cash?: number;
  reinvest_nav?: number;
  ratio?: number;
  status?: string;
  notes?: string;
}
