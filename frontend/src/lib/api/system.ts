import { request } from "./client";
import { TradingCalendarDay, DataSourceConfig } from "@/types/system";

export const systemApi = {
  getTradingCalendar: (year: number) =>
    request<TradingCalendarDay[]>({ method: "GET", url: "/trading-calendar", params: { year } }),

  syncTradingCalendar: (year: number) =>
    request<{ synced_count: number; year: number; message: string }>({
      method: "POST",
      url: "/trading-calendar/sync",
      data: { year },
    }),

  getDataSourceConfig: () =>
    request<DataSourceConfig[]>({ method: "GET", url: "/system/data-sources" }),

  // 后端按数据源名称分别更新：tushare 只消费 api_key，akshare 只消费 is_enabled
  updateDataSource: (name: "tushare" | "akshare", data: { api_key?: string; is_enabled?: boolean }) =>
    request<{ message: string; name: string; is_enabled?: boolean }>({
      method: "PUT",
      url: `/system/data-sources/${name}`,
      data,
    }),
};
