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

// 字段与后端 schemas 的 SubscriptionUpdate 对齐：
// 不含 confirm_date/status（后端会静默丢弃）；改状态请走 confirm/unconfirm/cancel 端点
// apply_date 可改（issue #202）：后端校验交易日/快照日并重算预计确认日
// notes 传 null 清除备注（唯一放行 null 的字段，其余字段 null 拒 INVALID_PARAM，PR #204 评审）
export interface SubscriptionUpdate {
  platform_code?: string;
  amount?: number;
  shares?: number;
  unit_price?: number;
  apply_date?: string;
  notes?: string | null;
}

// 确认前预览（#248）：与真实确认共用后端计算实现
export interface SubscriptionPreviewResult {
  nav: number;
  shares?: number;
  amount?: number;
  confirm_date: string;
  is_first: boolean;
}

export interface SubscriptionPreviewResponse {
  subscription: Subscription;
  preview: SubscriptionPreviewResult;
}
