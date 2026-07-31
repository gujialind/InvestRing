"use client";

import MainLayout from "@/components/layout/MainLayout";
import AdminGuard from "@/components/shared/AdminGuard";
import ProductsContent from "@/components/shared/ProductsContent";

export default function ProductsPage() {
  return (
    <MainLayout>
      <AdminGuard>
        <ProductsContent />
      </AdminGuard>
    </MainLayout>
  );
}
