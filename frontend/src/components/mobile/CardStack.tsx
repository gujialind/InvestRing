"use client";

import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";

interface CardStackItem {
  id: string | number;
  content: React.ReactNode;
}

interface CardStackProps {
  items: CardStackItem[];
  className?: string;
  gap?: number;
}

export default function CardStack({ items, className, gap = 4 }: CardStackProps) {
  if (!items || items.length === 0) {
    return (
      <div className="text-center text-muted-foreground py-8">
        暂无数据
      </div>
    );
  }

  return (
    <div className={cn("space-y-" + gap, className)}>
      {items.map((item) => (
        <Card key={item.id}>
          <CardContent className="p-4">{item.content}</CardContent>
        </Card>
      ))}
    </div>
  );
}