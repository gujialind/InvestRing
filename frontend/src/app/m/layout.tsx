"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import MobileLayout from "@/components/mobile/MobileLayout";

export default function MobileRootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated } = useAuthStore();
  // issue #68：persist 水合竞态——首帧 isAuthenticated 恒为初始值 false，
  // 必须等 localStorage 水合完成后再做鉴权判断，否则刷新会被误踢回登录页。
  // 逻辑与 PC 侧 MainLayout 保持一致。
  const [hydrated, setHydrated] = useState(false);

  // 登录页不受鉴权守卫约束（否则未登录时登录页自身被拦截，渲染空白）
  const isLoginPage = pathname === "/m/login";

  useEffect(() => {
    const unsub = useAuthStore.persist?.onFinishHydration?.(() => setHydrated(true));
    setHydrated(useAuthStore.persist?.hasHydrated?.() ?? true);
    return unsub;
  }, []);

  useEffect(() => {
    if (hydrated && !isAuthenticated && !isLoginPage) {
      router.replace("/m/login");
    }
  }, [hydrated, isAuthenticated, isLoginPage, router]);

  // 登录页：不套 MobileLayout（无需底部导航），直接渲染
  if (isLoginPage) {
    return <>{children}</>;
  }

  if (!hydrated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return <MobileLayout>{children}</MobileLayout>;
}
