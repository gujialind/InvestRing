"use client";

import { ReactNode } from "react";
import { useRoleCheck } from "@/hooks/useAuth";
import EmptyState from "@/components/shared/EmptyState";

/**
 * 管理员页面守卫：viewer 直接输入 URL 访问 admin 页面时给出友好提示，
 * 不再渲染操作按钮 + 一串 403 toast（后端权限是硬校验，此处仅体验层防护）。
 * 布局层（MainLayout / m/layout）已处理 persist 水合，此处可直接读角色。
 */
export default function AdminGuard({ children }: { children: ReactNode }) {
  const { isAdmin } = useRoleCheck();

  if (!isAdmin) {
    return (
      <EmptyState
        message="无权限访问"
        description="该页面仅管理员可用，请联系管理员或返回首页"
      />
    );
  }

  return <>{children}</>;
}
