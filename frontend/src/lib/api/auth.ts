import { request } from "./client";
import {
  LoginRequest,
  LoginResponse,
  ChangePasswordRequest,
  UserInfo,
} from "@/types/auth";

export const authApi = {
  login: (data: LoginRequest) =>
    request<LoginResponse>({ method: "POST", url: "/auth/login", data }),

  // 后端会将 token 加入黑名单并记录登出日志，需在本地清理 token 前调用
  logout: () =>
    request<{ message: string }>({ method: "POST", url: "/auth/logout" }),

  changePassword: (data: ChangePasswordRequest) =>
    request<{ message: string }>({ method: "PUT", url: "/auth/password", data }),

  getCurrentUser: () =>
    request<UserInfo>({ method: "GET", url: "/auth/me" }),
};
