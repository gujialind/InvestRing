export interface Subscription {
  id: number;
  portfolio_code: string;
  investor_code: string;
  platform_code: string;
  sub_type: string;
  amount?: number;
  shares?: number;
  unit_price?: number;
  apply_date: string;
  confirm_date?: string;
  status: string;
  notes?: string;
  created_at?: string;
  updated_at?: string;
}

export interface SubscriptionCreate {
  portfolio_code: string;
  investor_code: string;
  platform_code: string;
  sub_type: string;
  amount?: number;
  shares?: number;
  unit_price?: number;
  apply_date: string;
  notes?: string;
}

export interface SubscriptionUpdate {
  platform_code?: string;
  amount?: number;
  shares?: number;
  unit_price?: number;
  confirm_date?: string;
  status?: string;
  notes?: string;
}
