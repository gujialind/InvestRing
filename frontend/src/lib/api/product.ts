import { request } from "./client";
import { Product, ProductCreate, ProductUpdate } from "@/types/product";
import { PaginatedResponse } from "@/types/common";

export interface PriceDataPoint {
  product_code: string;
  market: string;
  date: string;
  unit_price: number;
}

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
    request<PriceDataPoint[]>({
      method: "GET",
      url: `/market-data/products/${code}/${market}/price-data`,
      params,
    }),
};
