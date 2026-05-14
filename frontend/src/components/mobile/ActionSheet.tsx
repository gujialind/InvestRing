"use client";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";

interface ActionItem {
  id: string;
  label: string;
  icon?: React.ReactNode;
  onClick: () => void;
  variant?: "default" | "destructive" | "outline";
}

interface ActionSheetProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  actions: ActionItem[];
}

export default function ActionSheet({ isOpen, onClose, title, actions }: ActionSheetProps) {
  if (!isOpen) return null;

  return (
    <>
      <div className="fixed inset-0 bg-black/50 z-50" onClick={onClose} />
      <div
        className={cn(
          "fixed bottom-0 left-0 right-0 z-50 bg-background rounded-t-xl p-4 pb-8",
          "animate-in slide-in-from-bottom duration-300"
        )}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">{title || "操作"}</h3>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="space-y-2">
          {actions.map((action) => (
            <Button
              key={action.id}
              variant={action.variant || "default"}
              className="w-full justify-start"
              onClick={() => {
                action.onClick();
                onClose();
              }}
            >
              {action.icon}
              {action.label}
            </Button>
          ))}
        </div>
      </div>
    </>
  );
}