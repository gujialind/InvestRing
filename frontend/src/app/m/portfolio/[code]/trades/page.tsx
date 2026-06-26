"use client";

import MobileLayout from "@/components/mobile/MobileLayout";
import TradesContent from "@/components/shared/TradesContent";

export default function MobileTradesPage() {
  return (
    <MobileLayout>
      <TradesContent basePath="/m/portfolio" variant="mobile" />
    </MobileLayout>
  );
}
