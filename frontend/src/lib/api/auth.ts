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

  changePassword: (data: ChangePasswordRequest) =>
    request<{ message: string }>({ method: "POST", url: "/auth/password", data }),

  getCurrentUser: () =>
    request<UserInfo>({ method: "GET", url: "/auth/me" }),
};
