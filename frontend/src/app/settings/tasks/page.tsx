"use client";

import MainLayout from "@/components/layout/MainLayout";
import AdminGuard from "@/components/shared/AdminGuard";
import TasksContent from "@/components/shared/TasksContent";

export default function TasksPage() {
  return (
    <MainLayout>
      <AdminGuard>
        <TasksContent />
      </AdminGuard>
    </MainLayout>
  );
}
