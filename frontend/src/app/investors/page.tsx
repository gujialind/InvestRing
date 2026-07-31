"use client";

import MainLayout from "@/components/layout/MainLayout";
import AdminGuard from "@/components/shared/AdminGuard";
import InvestorsContent from "@/components/shared/InvestorsContent";

export default function InvestorsPage() {
  return (
    <MainLayout>
      <AdminGuard>
        <InvestorsContent />
      </AdminGuard>
    </MainLayout>
  );
}
