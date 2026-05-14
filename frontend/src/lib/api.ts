import axios, { AxiosError, AxiosInstance, AxiosRequestConfig, AxiosResponse } from "axios";
import { ApiError, ApiErrorDetail, PaginatedResponse } from "@/types/common";
import {
  LoginRequest,
  LoginResponse,
  ChangePasswordRequest,
  UserInfo,
} from "@/types/auth";
import {
  Portfolio,
  PortfolioCreate,
  PortfolioUpdate,
  PortfolioValueSnapshot,
} from "@/types/portfolio";
import {
  Investor,
  InvestorCreate,
  InvestorUpdate,
} from "@/types/investor";
import {
  Product,
  ProductCreate,
  ProductUpdate,
} from "@/types/product";
import {
  Trade,
  TradeCreate,
  TradeUpdate,
} from "@/types/trade";
import {
  Subscription,
  SubscriptionCreate,
  SubscriptionUpdate,
} from "@/types/subscription";
import {
  Position,
  PositionCreate,
  PositionUpdate,
} from "@/types/position";

// 创建 axios 实例
const api: AxiosInstance = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "/api",
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000,
});

// 请求拦截器：自动附加 Token
api.interceptors.request.use(
  (config) => {
    // 仅在客户端环境读取 token
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("token");
      if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器：统一错误处理 + 401 跳转
api.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError<ApiError>) => {
    if (typeof window !== "undefined") {
      if (error.response?.status === 401) {
        localStorage.removeItem("token");
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// 统一错误处理封装
export class ApiException extends Error {
  public code: string;
  public status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
    this.name = "ApiException";
  }
}

export function handleApiError(error: unknown): ApiException {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiError>;
    const status = axiosError.response?.status || 500;
    const detail = axiosError.response?.data?.detail;
    const code = detail?.error || "UNKNOWN_ERROR";
    const message = detail?.message || axiosError.message || "请求失败";
    return new ApiException(code, message, status);
  }
  if (error instanceof Error) {
    return new ApiException("UNKNOWN_ERROR", error.message, 500);
  }
  return new ApiException("UNKNOWN_ERROR", "未知错误", 500);
}

// 通用请求封装
async function request<T>(config: AxiosRequestConfig): Promise<T> {
  try {
    const response = await api.request<T>(config);
    return response.data;
  } catch (error) {
    throw handleApiError(error);
  }
}

// ==================== 认证模块 ====================
export const authApi = {
  login: (data: LoginRequest) =>
    request<LoginResponse>({ method: "POST", url: "/auth/login", data }),

  changePassword: (data: ChangePasswordRequest) =>
    request<{ message: string }>({ method: "POST", url: "/auth/password", data }),

  getCurrentUser: () =>
    request<UserInfo>({ method: "GET", url: "/auth/me" }),
};

// ==================== 投资人管理 ====================
export const investorApi = {
  list: (params?: { page?: number; page_size?: number }) =>
    request<PaginatedResponse<Investor>>({ method: "GET", url: "/investors", params }),

  get: (code: string) =>
    request<Investor>({ method: "GET", url: `/investors/${code}` }),

  create: (data: InvestorCreate) =>
    request<Investor>({ method: "POST", url: "/investors", data }),

  update: (code: string, data: InvestorUpdate) =>
    request<Investor>({ method: "PUT", url: `/investors/${code}`, data }),

  remove: (code: string) =>
    request<{ message: string }>({ method: "DELETE", url: `/investors/${code}` }),
};

// ==================== 组合管理 ====================
export const portfolioApi = {
  list: (params?: { page?: number; page_size?: number; status?: string }) =>
    request<PaginatedResponse<Portfolio>>({ method: "GET", url: "/portfolios", params }),

  get: (code: string) =>
    request<Portfolio>({ method: "GET", url: `/portfolios/${code}` }),

  create: (data: PortfolioCreate) =>
    request<Portfolio>({ method: "POST", url: "/portfolios", data }),

  update: (code: string, data: PortfolioUpdate) =>
    request<Portfolio>({ method: "PUT", url: `/portfolios/${code}`, data }),

  close: (code: string) =>
    request<Portfolio>({ method: "POST", url: `/portfolios/${code}/close` }),

  activate: (code: string) =>
    request<Portfolio>({ method: "POST", url: `/portfolios/${code}/reactivate` }),

  remove: (code: string) =>
    request<{ message: string }>({ method: "DELETE", url: `/portfolios/${code}` }),

  getSnapshots: (code: string, params?: { page?: number; page_size?: number }) =>
    request<PaginatedResponse<PortfolioValueSnapshot>>({
      method: "GET",
      url: `/portfolios/${code}/snapshots`,
      params,
    }),

  getLatestSnapshot: (code: string) =>
    request<PortfolioValueSnapshot>({ method: "GET", url: `/portfolios/${code}/snapshots/latest` }),

  getAvailableCash: (code: string) =>
    request<{ available_cash: number }>({ method: "GET", url: `/positions/portfolio/${code}/available-cash` }),

  getInvestors: (code: string) =>
    request<{ investor_code: string; name: string; shares: number }[]>({
      method: "GET",
      url: `/portfolios/${code}/investors`,
    }),
};

// ==================== 持仓管理 ====================
export const positionApi = {
  list: (portfolioCode: string, params?: { page?: number; page_size?: number; snapshot_date?: string }) =>
    request<PaginatedResponse<Position>>({
      method: "GET",
      url: `/positions`,
      params: { portfolio_code: portfolioCode, ...params },
    }),

  getLatest: (portfolioCode: string) =>
    request<Position[]>({ method: "GET", url: `/portfolios/${portfolioCode}/positions/latest` }),

  create: (data: PositionCreate) =>
    request<Position>({ method: "POST", url: "/positions", data }),

  update: (id: number, data: PositionUpdate) =>
    request<Position>({ method: "PUT", url: `/positions/${id}`, data }),

  getAttribution: (portfolioCode: string) =>
    request<{ asset_type: string; value: number; weight: number }[]>({
      method: "GET",
      url: `/portfolios/${portfolioCode}/attribution`,
    }),
};

// ==================== 申购赎回管理 ====================
export const subscriptionApi = {
  list: (params?: { page?: number; page_size?: number; portfolio_code?: string; status?: string }) =>
    request<PaginatedResponse<Subscription>>({ method: "GET", url: "/subscriptions", params }),

  get: (id: number) =>
    request<Subscription>({ method: "GET", url: `/subscriptions/${id}` }),

  create: (data: SubscriptionCreate) =>
    request<Subscription>({ method: "POST", url: "/subscriptions", data }),

  confirm: (id: number, data?: { confirm_date?: string; unit_price?: number }) =>
    request<Subscription>({ method: "POST", url: `/subscriptions/${id}/confirm`, data }),

  cancel: (id: number) =>
    request<Subscription>({ method: "POST", url: `/subscriptions/${id}/cancel` }),
};

// ==================== 调仓交易管理 ====================
export const tradeApi = {
  list: (params?: { page?: number; page_size?: number; portfolio_code?: string; status?: string }) =>
    request<PaginatedResponse<Trade>>({ method: "GET", url: "/trades", params }),

  get: (id: number) =>
    request<Trade>({ method: "GET", url: `/trades/${id}` }),

  create: (data: TradeCreate) =>
    request<Trade>({ method: "POST", url: "/trades", data }),

  update: (id: number, data: TradeUpdate) =>
    request<Trade>({ method: "PUT", url: `/trades/${id}`, data }),

  confirm: (id: number, data?: { confirm_date?: string; price?: number }) =>
    request<Trade>({ method: "POST", url: `/trades/${id}/confirm`, data }),

  cancel: (id: number) =>
    request<Trade>({ method: "POST", url: `/trades/${id}/cancel` }),

  batchRebalance: (portfolioCode: string, trades: TradeCreate[], idempotencyKey?: string) =>
    request<{ created_trades: Trade[] }>({
      method: "POST",
      url: `/portfolios/${portfolioCode}/batch-rebalance`,
      data: { trades },
      headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined,
    }),
};

// ==================== 产品管理 ====================
export const productApi = {
  list: (params?: { page?: number; page_size?: number; product_type?: string }) =>
    request<PaginatedResponse<Product>>({ method: "GET", url: "/products", params }),

  get: (code: string, market?: string) =>
    request<Product>({ method: "GET", url: `/products/${code}`, params: market ? { market } : undefined }),

  create: (data: ProductCreate) =>
    request<Product>({ method: "POST", url: "/products", data }),

  update: (code: string, data: ProductUpdate, market?: string) =>
    request<Product>({ method: "PUT", url: `/products/${code}/${market || ""}`, data }),

  delete: (code: string, market?: string) =>
    request<{ message: string }>({ method: "DELETE", url: `/products/${code}/${market || ""}` }),

  syncPrice: (code: string, market?: string, data?: { start_date?: string; end_date?: string }) =>
    request<{ message: string; synced_count?: number }>({
      method: "POST",
      url: `/market-data/products/${code}/${market || ""}/sync-price-data`,
      data,
    }),

  syncHistory: (code: string, market?: string) =>
    request<{ message: string; synced_count?: number }>({
      method: "POST",
      url: `/market-data/products/${code}/${market || ""}/sync-history`,
    }),

  getPriceData: (code: string, market: string, params?: { start_date?: string; end_date?: string; limit?: number }) =>
    request<Array<{ product_code: string; market: string; date: string; unit_price: number }>>({
      method: "GET",
      url: `/market-data/products/${code}/${market}/price-data`,
      params,
    }),

};

// ==================== 平台管理 ====================
export interface Platform {
  code: string;
  name: string;
  platform_type?: string;
  created_at?: string;
}

export interface PlatformCreate {
  code: string;
  name: string;
  platform_type?: string;
}

export interface PlatformUpdate {
  name?: string;
  platform_type?: string;
}

export const platformApi = {
  list: (params?: { page?: number; page_size?: number }) =>
    request<PaginatedResponse<Platform>>({ method: "GET", url: "/platforms", params }),

  get: (code: string) =>
    request<Platform>({ method: "GET", url: `/platforms/${code}` }),

  create: (data: PlatformCreate) =>
    request<Platform>({ method: "POST", url: "/platforms", data }),

  update: (code: string, data: PlatformUpdate) =>
    request<Platform>({ method: "PUT", url: `/platforms/${code}`, data }),

  delete: (code: string) =>
    request<{ message: string }>({ method: "DELETE", url: `/platforms/${code}` }),
};

// ==================== 系统管理 ====================
export interface TradingCalendarDay {
  date: string;
  is_open: boolean;
  week_day: number;
  notes?: string;
}

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
    request<Array<{ name: string; api_key?: string; is_enabled: boolean; last_sync_at?: string }>>({ method: "GET", url: "/system/data-sources" }),

  updateDataSourceConfig: (data: { source: string; config: Record<string, string> }) =>
    request<{ message: string }>({ method: "PUT", url: `/system/data-sources/${data.source}`, data: { api_key: data.config.token, is_enabled: data.config.akshare_enabled === "true" } }),
};

// ==================== 日志与任务 ====================
export interface LogEntry {
  id: number;
  action: string;
  details?: string;
  created_at: string;
  user_code?: string;
}

export interface TaskExecution {
  id: number;
  task_code: string;
  status: string;
  started_at: string;
  finished_at?: string;
  error_message?: string;
}

export interface NotificationItem {
  id: number;
  title: string;
  content: string;
  status: string;
  is_read?: boolean;
  created_at: string;
}

export const logApi = {
  loginLogs: (params?: { page?: number; page_size?: number }) =>
    request<any[]>({ method: "GET", url: "/system/logs/login", params }),

  auditLogs: (params?: { page?: number; page_size?: number }) =>
    request<any[]>({ method: "GET", url: "/system/logs/audit", params }),

  errorLogs: (params?: { page?: number; page_size?: number }) =>
    request<any[]>({ method: "GET", url: "/system/logs/error", params }),

  taskLogs: (params?: { page?: number; page_size?: number }) =>
    request<any[]>({ method: "GET", url: "/system/logs/task", params }),
};

export const taskApi = {
  list: () =>
    request<any[]>({ method: "GET", url: "/system/tasks" }),

  run: (code: string) =>
    request<{ message: string }>({ method: "POST", url: `/system/tasks/${code}/run` }),

  enable: (code: string) =>
    request<{ message: string }>({ method: "POST", url: `/system/tasks/${code}/enable` }),

  disable: (code: string) =>
    request<{ message: string }>({ method: "POST", url: `/system/tasks/${code}/disable` }),

  executionHistory: (params?: { task_code?: string; page?: number; page_size?: number }) =>
    request<any[]>({ method: "GET", url: "/system/tasks/executions", params }),
};

export const notificationApi = {
  list: (params?: { page?: number; page_size?: number; status?: string }) =>
    request<PaginatedResponse<NotificationItem>>({ method: "GET", url: "/system/notifications", params }),

  markAsRead: (id: number) =>
    request<{ message: string }>({ method: "POST", url: `/system/notifications/${id}/read` }),

  markAllAsRead: () =>
    request<{ message: string }>({ method: "POST", url: "/system/notifications/read-all" }),
};

export default api;
