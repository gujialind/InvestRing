"use client";

import { useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/authStore";
import { authApi } from "@/lib/api";
import { LoginRequest, ChangePasswordRequest } from "@/types/auth";
import { useUIStore } from "@/stores/uiStore";

// 登录 Hook
export function useLogin() {
  const router = useRouter();
  const login = useAuthStore((state) => state.login);
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (data: LoginRequest) => authApi.login(data),
    onSuccess: (data) => {
      login(data.token, data.user);
      addToast({
        type: "success",
        title: "登录成功",
        message: `欢迎回来，${data.user.name}`,
      });
      router.push("/dashboard");
    },
    onError: (error: any) => {
      addToast({
        type: "error",
        title: "登录失败",
        message: error.message || "用户名或密码错误",
      });
    },
  });
}

// 登出 Hook
export function useLogout() {
  const router = useRouter();
  const logout = useAuthStore((state) => state.logout);
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  return useCallback(() => {
    logout();
    queryClient.clear();
    addToast({
      type: "info",
      title: "已退出登录",
    });
    router.push("/login");
  }, [logout, queryClient, router, addToast]);
}

// 获取当前用户 Hook
export function useCurrentUser() {
  const token = useAuthStore((state) => state.token);
  const setUser = useAuthStore((state) => state.setUser);

  return useQuery({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      const user = await authApi.getCurrentUser();
      setUser(user);
      return user;
    },
    enabled: !!token,
    staleTime: 5 * 60 * 1000, // 5 分钟
  });
}

// 修改密码 Hook
export function useChangePassword() {
  const addToast = useUIStore((state) => state.addToast);

  return useMutation({
    mutationFn: (data: ChangePasswordRequest) => authApi.changePassword(data),
    onSuccess: () => {
      addToast({
        type: "success",
        title: "密码修改成功",
        message: "请使用新密码重新登录",
      });
    },
    onError: (error: any) => {
      addToast({
        type: "error",
        title: "密码修改失败",
        message: error.message || "请检查原密码是否正确",
      });
    },
  });
}

// 认证守卫 Hook
export function useAuthGuard(requireAuth: boolean = true) {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isLoading = useAuthStore((state) => state.isLoading);

  useEffect(() => {
    if (isLoading) return;

    if (requireAuth && !isAuthenticated) {
      router.replace("/login");
    }

    if (!requireAuth && isAuthenticated) {
      router.replace("/dashboard");
    }
  }, [isAuthenticated, isLoading, requireAuth, router]);

  return { isAuthenticated, isLoading };
}

// 角色权限检查 Hook
export function useRoleCheck() {
  const user = useAuthStore((state) => state.user);

  const isAdmin = user?.role === "admin";
  const isViewer = user?.role === "viewer";

  const checkRole = useCallback(
    (allowedRoles: string[]) => {
      if (!user) return false;
      return allowedRoles.includes(user.role);
    },
    [user]
  );

  return { isAdmin, isViewer, role: user?.role, checkRole };
}
