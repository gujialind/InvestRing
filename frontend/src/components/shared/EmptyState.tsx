"use client";

import { ReactNode } from "react";

interface EmptyStateProps {
  message: string;
  description?: string;
  action?: ReactNode;
}

/**
 * 统一空态展示。
 */
export default function EmptyState({ message, description, action }: EmptyStateProps) {
  return (
    <div className="text-center text-muted-foreground py-8">
      <p>{message}</p>
      {description && <p className="text-xs mt-1">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
