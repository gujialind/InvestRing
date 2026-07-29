import axios, { AxiosError, AxiosInstance, AxiosRequestConfig, AxiosResponse } from "axios";
import { ApiError } from "@/types/common";

/**
 * 检测运行时基础路径（用于 ModelScope Studio 等子路径部署场景）。
 * 魔搭 Studio 将应用挂载在 /studios/{owner}/{repo}/ 下，
 * 平台反向代理会剥离前缀后转发给容器，但浏览器端发起的 API 请求
 * 必须携带完整前缀才能经代理抵达本应用的 Next.js 服务器。
 */
export function getBasePath(): string {
  if (typeof window === "undefined") return "";
  const match = window.location.pathname.match(/^(\/studios\/[^/]+\/[^/]+)/);
  return match ? match[1] : "";
}

// 创建 axios 实例
const api: AxiosInstance = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || `${getBasePath()}/api`,
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
        window.location.href = `${getBasePath()}/login`;
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
export async function request<T>(config: AxiosRequestConfig): Promise<T> {
  try {
    const response = await api.request<T>(config);
    return response.data;
  } catch (error) {
    throw handleApiError(error);
  }
}

/**
 * 从未知错误中提取用户可读消息。
 * 覆盖 ApiException / Error / axios 错误结构，失败时返回 fallback。
 * 用于 React Query 的 onError 回调，避免使用 any。
 */
export function getErrorMessage(error: unknown, fallback = "操作失败"): string {
  if (error instanceof Error && error.message) return error.message;
  const e = error as { response?: { data?: { detail?: { message?: string } } }; message?: string };
  return e?.response?.data?.detail?.message || e?.message || fallback;
}

export default api;
