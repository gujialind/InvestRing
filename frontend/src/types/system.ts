export interface TradingCalendarDay {
  date: string;
  is_open: boolean;
  week_day: number;
  notes?: string;
}

export interface DataSourceConfig {
  name: string;
  api_key?: string;
  is_enabled: boolean;
  last_sync_at?: string;
}
