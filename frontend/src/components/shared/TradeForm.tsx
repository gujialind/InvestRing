"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DatePicker } from "@/components/ui/date-picker";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Loader2 } from "lucide-react";
import { toDateOnly, parseDateOnly } from "@/lib/utils";
import { usePlatformList } from "@/hooks/usePlatform";

interface TradeFormProps {
  portfolioCode: string;
  onSubmit: (data: TradeFormData) => void;
  isSubmitting?: boolean;
}

export interface TradeFormData {
  trade_type: "buy" | "sell";
  product_code: string;
  platform_code?: string;
  amount?: number;
  shares?: number;
  price?: number;
  trade_date: string;
}

export default function TradeForm({ portfolioCode, onSubmit, isSubmitting }: TradeFormProps) {
  const [tradeType, setTradeType] = useState<"buy" | "sell">("buy");
  const { data: platformsData } = usePlatformList({ page_size: 100 });
  const platforms = platformsData?.items || [];
  const [formData, setFormData] = useState({
    product_code: "",
    platform_code: "",
    amount: "",
    shares: "",
    price: "",
    trade_date: toDateOnly(new Date()),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      trade_type: tradeType,
      product_code: formData.product_code,
      platform_code: formData.platform_code || undefined,
      price: formData.price ? parseFloat(formData.price) : undefined,
      trade_date: formData.trade_date,
      ...(tradeType === "buy"
        ? { amount: parseFloat(formData.amount) }
        : { shares: parseFloat(formData.shares) }),
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>调仓交易</CardTitle>
        <CardDescription>组合: {portfolioCode}</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex gap-2">
            <Button
              type="button"
              variant={tradeType === "buy" ? "default" : "outline"}
              onClick={() => setTradeType("buy")}
              className="flex-1"
            >
              买入
            </Button>
            <Button
              type="button"
              variant={tradeType === "sell" ? "default" : "outline"}
              onClick={() => setTradeType("sell")}
              className="flex-1"
            >
              卖出
            </Button>
          </div>
          <div className="space-y-2">
            <Label htmlFor="product_code">产品代码</Label>
            <Input
              id="product_code"
              value={formData.product_code}
              onChange={(e) => setFormData({ ...formData, product_code: e.target.value })}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="platform_code">交易平台</Label>
            <select
              id="platform_code"
              value={formData.platform_code}
              onChange={(e) => setFormData({ ...formData, platform_code: e.target.value })}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <option value="">请选择平台</option>
              {platforms.map((plat) => (
                <option key={plat.code} value={plat.code}>
                  {plat.name} ({plat.code})
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="price">价格</Label>
            <Input
              id="price"
              type="number"
              step="0.0001"
              value={formData.price}
              onChange={(e) => setFormData({ ...formData, price: e.target.value })}
              placeholder="可选，确认时填写"
            />
          </div>
          {tradeType === "buy" ? (
            <div className="space-y-2">
              <Label htmlFor="amount">买入金额</Label>
              <Input
                id="amount"
                type="number"
                step="0.01"
                value={formData.amount}
                onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                required
              />
            </div>
          ) : (
            <div className="space-y-2">
              <Label htmlFor="shares">卖出份额</Label>
              <Input
                id="shares"
                type="number"
                step="0.01"
                value={formData.shares}
                onChange={(e) => setFormData({ ...formData, shares: e.target.value })}
                required
              />
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="trade_date">交易日期</Label>
            <DatePicker
              date={parseDateOnly(formData.trade_date)}
              onSelect={(date) => {
                setFormData({ ...formData, trade_date: toDateOnly(date) })
              }}
            />
          </div>
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            提交
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}