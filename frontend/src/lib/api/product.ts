import { request, ApiException } from "./client";
import { Product, ProductCreate, ProductUpdate } from "@/types/product";
import { PaginatedResponse } from "@/types/common";

export interface PriceDataPoint {
  product_code: string;
  market: string;
  price_date: string;
  unit_price: number;
}

/**
 * market 是后端必填路径参数：缺失时抛 ApiException 而不是拼出 `/products/CODE/` 这类
 * 带空段的畸形 URL（会得到令人困惑的 307/404/405）。
 */
function requireMarket(market: string | undefined, action: string): string {
  if (!market) {
    throw new ApiException(
      "MARKET_REQUIRED",
      `${action}需指定市场（market），现金类产品不支持此操作`,
      422
    );
  }
  return market;
}

export const productApi = {
  list: (params?: { page?: number; page_size?: number; product_type?: string }) =>
    request<PaginatedResponse<Product>>({ method: "GET", url: "/products", params }),

  // 后端两个端点：/products/{code}/{market} 精确匹配；/products/{code} 自动解析（一码多市场时抛 MARKET_AMBIGUOUS）。
  // market 不能用 query 传（后端不接收，会被忽略）
  get: (code: string, market?: string) =>
    request<Product>({ method: "GET", url: market ? `/products/${code}/${market}` : `/products/${code}` }),

  create: (data: ProductCreate) =>
    request<Product>({ method: "POST", url: "/products", data }),

  // 以下端点 market 为必填路径参数，缺失时尽早报错而不是发出尾部带空段的畸形 URL
  update: (code: string, data: ProductUpdate, market?: string) =>
    request<Product>({ method: "PUT", url: `/products/${code}/${requireMarket(market, "更新产品")}`, data }),

  delete: (code: string, market?: string) =>
    request<{ message: string }>({ method: "DELETE", url: `/products/${code}/${requireMarket(market, "删除产品")}` }),

  syncPrice: (code: string, market?: string, data?: { start_date?: string; end_date?: string }) =>
    request<{ message: string; synced_count?: number }>({
      method: "POST",
      url: `/market-data/products/${code}/${requireMarket(market, "同步价格")}/sync-price-data`,
      data,
    }),

  syncHistory: (code: string, market?: string) =>
    request<{ message: string; synced_count?: number }>({
      method: "POST",
      url: `/market-data/products/${code}/${requireMarket(market, "同步历史价格")}/sync-history`,
    }),

  getPriceData: (code: string, market: string, params?: { start_date?: string; end_date?: string; limit?: number }) =>
    request<PriceDataPoint[]>({
      method: "GET",
      url: `/market-data/products/${code}/${market}/price-data`,
      params,
    }),
};
