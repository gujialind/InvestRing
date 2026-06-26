"use client";

import MainLayout from "@/components/layout/MainLayout";
import PortfolioListContent from "@/components/shared/PortfolioListContent";

export default function PortfoliosPage() {
  return (
    <MainLayout>
      <PortfolioListContent basePath="/portfolio" variant="desktop" />
    </MainLayout>
  );
}
