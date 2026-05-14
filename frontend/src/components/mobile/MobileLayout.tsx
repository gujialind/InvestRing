"use client";

import BottomNav from "./BottomNav";

export default function MobileLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background pb-16">
      <main className="p-4">{children}</main>
      <BottomNav />
    </div>
  );
}