"use client";

import MainLayout from "@/components/layout/MainLayout";
import SubscriptionsContent from "@/components/shared/SubscriptionsContent";

export default function SubscriptionsPage() {
  return (
    <MainLayout>
      <SubscriptionsContent basePath="/portfolio" variant="desktop" />
    </MainLayout>
  );
}
