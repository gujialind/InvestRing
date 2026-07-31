"use client";

import MainLayout from "@/components/layout/MainLayout";
import AdminGuard from "@/components/shared/AdminGuard";
import PlatformsContent from "@/components/shared/PlatformsContent";

export default function PlatformsPage() {
  return (
    <MainLayout>
      <AdminGuard>
        <PlatformsContent />
      </AdminGuard>
    </MainLayout>
  );
}
