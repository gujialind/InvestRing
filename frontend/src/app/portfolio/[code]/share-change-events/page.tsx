"use client";

import MainLayout from "@/components/layout/MainLayout";
import ShareChangeEventsContent from "@/components/shared/ShareChangeEventsContent";

export default function ShareChangeEventsPage() {
  return (
    <MainLayout>
      <ShareChangeEventsContent basePath="/portfolio" variant="desktop" />
    </MainLayout>
  );
}
