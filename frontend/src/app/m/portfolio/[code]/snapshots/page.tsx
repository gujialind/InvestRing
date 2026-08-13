"use client";

import AdminGuard from "@/components/shared/AdminGuard";
import SnapshotsContent from "@/components/shared/SnapshotsContent";

export default function MobilePortfolioSnapshotsPage() {
  return (
    <AdminGuard>
      <SnapshotsContent basePath="/m/portfolio" variant="mobile" />
    </AdminGuard>
  );
}
