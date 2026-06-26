"use client";

import MobileLayout from "@/components/mobile/MobileLayout";
import SubscriptionsContent from "@/components/shared/SubscriptionsContent";

export default function MobileSubscriptionsPage() {
  return (
    <MobileLayout>
      <SubscriptionsContent basePath="/m/portfolio" variant="mobile" />
    </MobileLayout>
  );
}
