"use client";

import MainLayout from "@/components/layout/MainLayout";
import AdminGuard from "@/components/shared/AdminGuard";
import AssetClassificationsContent from "@/components/shared/AssetClassificationsContent";

export default function AssetClassificationsPage() {
  return (
    <MainLayout>
      <AdminGuard>
        <AssetClassificationsContent variant="desktop" />
      </AdminGuard>
    </MainLayout>
  );
}
