"use client";

import AdminGuard from "@/components/shared/AdminGuard";
import AssetClassificationsContent from "@/components/shared/AssetClassificationsContent";

// 薄壳页：MobileLayout 由 app/m/layout.tsx 统一提供，此处只渲染共享内容
export default function MobileAssetClassificationsPage() {
  return (
    <AdminGuard>
      <AssetClassificationsContent variant="mobile" />
    </AdminGuard>
  );
}
