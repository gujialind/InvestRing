"use client";

import MobileLayout from "@/components/mobile/MobileLayout";
import PortfolioListContent from "@/components/shared/PortfolioListContent";

export default function MobilePortfolioListPage() {
  return (
    <MobileLayout>
      <PortfolioListContent basePath="/m/portfolio" variant="mobile" />
    </MobileLayout>
  );
}
