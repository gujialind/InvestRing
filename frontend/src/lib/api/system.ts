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

  updateDataSourceConfig: (data: { source: string; config: Record<string, string> }) =>
    request<{ message: string }>({
      method: "PUT",
      url: `/system/data-sources/${data.source}`,
      data: { api_key: data.config.token, is_enabled: data.config.akshare_enabled === "true" },
    }),
};
