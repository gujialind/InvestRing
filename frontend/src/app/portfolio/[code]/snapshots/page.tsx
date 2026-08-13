"use client";

import MainLayout from "@/components/layout/MainLayout";
import AdminGuard from "@/components/shared/AdminGuard";
import SnapshotsContent from "@/components/shared/SnapshotsContent";

export default function PortfolioSnapshotsPage() {
  return (
    <MainLayout>
      <AdminGuard>
        <SnapshotsContent basePath="/portfolio" variant="desktop" />
      </AdminGuard>
    </MainLayout>
  );
}
