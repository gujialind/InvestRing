// 字段与后端 TradingCalendarResponse 对齐（仅 calendar_date / is_open / created_at）；
// 星期几由前端由 calendar_date 推算，后端不返回
export interface TradingCalendarDay {
  calendar_date: string;
  is_open: boolean;
  created_at?: string;
}

export interface DataSourceConfig {
  name: string;
  api_key?: string;
  is_enabled: boolean;
  last_sync_at?: string;
}
