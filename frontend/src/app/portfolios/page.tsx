"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import MainLayout from "@/components/layout/MainLayout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Plus, Eye, TrendingUp, Users, Loader2, Power, PowerOff, Trash2 } from "lucide-react";
import { formatCurrency, formatReturnRate, getReturnColorClass } from "@/lib/utils";
import { usePortfolioList, useCreatePortfolio, useClosePortfolio, useActivatePortfolio, useDeletePortfolio } from "@/hooks/usePortfolio";
import { useRoleCheck } from "@/hooks/useAuth";

export default function PortfoliosPage() {
  const router = useRouter();
  const { data, isLoading, refetch } = usePortfolioList({ page_size: 100 });
  const createPortfolio = useCreatePortfolio();
  const closePortfolio = useClosePortfolio();
  const activatePortfolio = useActivatePortfolio();
  const deletePortfolio = useDeletePortfolio();
  const { isAdmin } = useRoleCheck();

  const portfolios = data?.items || [];

  const [filter, setFilter] = useState<string>("all");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [formData, setFormData] = useState({
    code: "",
    name: "",
    description: "",
  });

  const filteredPortfolios = portfolios.filter((p) => {
    if (filter === "all") return true;
    return p.status === filter;
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createPortfolio.mutate(formData, {
      onSuccess: (data) => {
        setIsDialogOpen(false);
        setFormData({ code: "", name: "", description: "" });
        router.push(`/portfolios/${data.code}`);
      },
    });
  };

  const handleClose = (code: string) => {
    if (confirm("确定要关闭该组合吗？关闭后无法再进行申购/赎回/调仓操作。")) {
      closePortfolio.mutate(code);
    }
  };

  const handleActivate = (code: string) => {
    if (confirm("确定要重新激活该组合吗？")) {
      activatePortfolio.mutate(code);
    }
  };

  const handleDelete = (code: string) => {
    if (confirm("确定要删除该组合吗？删除后不可恢复。")) {
      deletePortfolio.mutate(code);
    }
  };

  if (isLoading) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center h-[60vh]">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">组合管理</h1>
            <p className="text-muted-foreground">
              管理投资组合和查看收益
            </p>
          </div>
          {isAdmin && (
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="mr-2 h-4 w-4" />
                  创建组合
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>创建组合</DialogTitle>
                  <DialogDescription>
                    创建新的投资组合
                  </DialogDescription>
                </DialogHeader>
                <form onSubmit={handleSubmit}>
                  <div className="space-y-4 py-4">
                    <div className="space-y-2">
                      <Label htmlFor="code">组合代码</Label>
                      <Input
                        id="code"
                        value={formData.code}
                        onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                        placeholder="如: PORT001"
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="name">组合名称</Label>
                      <Input
                        id="name"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        placeholder="如: 稳健增长组合"
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="description">描述</Label>
                      <Input
                        id="description"
                        value={formData.description}
                        onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                        placeholder="可选"
                      />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button type="submit" disabled={createPortfolio.isPending}>
                      {createPortfolio.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                      创建组合
                    </Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>
          )}
        </div>

        <div className="flex items-center gap-4">
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="筛选状态" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部</SelectItem>
              <SelectItem value="active">活跃</SelectItem>
              <SelectItem value="draft">草稿</SelectItem>
              <SelectItem value="closed">已关闭</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredPortfolios.map((portfolio) => (
            <Card key={portfolio.code}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">{portfolio.name}</CardTitle>
                  <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    portfolio.status === "active"
                      ? "bg-green-100 text-green-800"
                      : portfolio.status === "draft"
                      ? "bg-yellow-100 text-yellow-800"
                      : "bg-gray-100 text-gray-800"
                  }`}>
                    {portfolio.status === "active" ? "活跃" : portfolio.status === "draft" ? "草稿" : "已关闭"}
                  </span>
                </div>
                <CardDescription>{portfolio.code}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {portfolio.status === "active" && (
                    <>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">总资产</span>
                        <span className="font-medium">{formatCurrency(portfolio.total_value || 0)}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">累计收益</span>
                        <span className={`font-medium ${getReturnColorClass(portfolio.cumulative_return || 0)}`}>
                          {formatReturnRate(portfolio.cumulative_return || 0)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">投资人</span>
                        <div className="flex items-center gap-1">
                          <Users className="h-4 w-4 text-muted-foreground" />
                          <span className="font-medium">{portfolio.investor_count || 0}</span>
                        </div>
                      </div>
                    </>
                  )}
                  {portfolio.status === "draft" && (
                    <div className="text-sm text-muted-foreground py-2">
                      组合尚未激活，请执行首次申购以启动组合
                    </div>
                  )}
                  <div className="flex gap-2 pt-2">
                    <Link href={`/portfolios/${portfolio.code}`} className="flex-1">
                      <Button variant="outline" className="w-full">
                        <Eye className="mr-2 h-4 w-4" />
                        详情
                      </Button>
                    </Link>
                    {isAdmin && portfolio.status === "active" && (
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={() => handleClose(portfolio.code)}
                        disabled={closePortfolio.isPending}
                        title="关闭组合"
                      >
                        <PowerOff className="h-4 w-4 text-red-500" />
                      </Button>
                    )}
                    {isAdmin && portfolio.status === "closed" && (
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={() => handleActivate(portfolio.code)}
                        disabled={activatePortfolio.isPending}
                        title="重新激活"
                      >
                        <Power className="h-4 w-4 text-green-500" />
                      </Button>
                    )}
                    {isAdmin && portfolio.status === "draft" && (
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={() => handleDelete(portfolio.code)}
                        disabled={deletePortfolio.isPending}
                        title="删除组合"
                      >
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {filteredPortfolios.length === 0 && (
          <div className="text-center text-muted-foreground py-12">
            暂无符合条件的组合
          </div>
        )}
      </div>
    </MainLayout>
  );
}
