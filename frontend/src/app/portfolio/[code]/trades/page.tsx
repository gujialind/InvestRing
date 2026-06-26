"use client";

import MainLayout from "@/components/layout/MainLayout";
import TradesContent from "@/components/shared/TradesContent";

export default function TradesPage() {
  return (
    <MainLayout>
      <TradesContent basePath="/portfolio" variant="desktop" />
    </MainLayout>
  );
}
