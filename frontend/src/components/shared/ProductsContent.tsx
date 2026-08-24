"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import Link from "next/link";
import { Plus, Pencil, Trash2, CheckCircle, XCircle, Loader2, RefreshCw, TrendingUp, Eye, Tags } from "lucide-react";
import { Product } from "@/types/product";
import { useUIStore } from "@/stores/uiStore";
import { formatNav } from "@/lib/utils";
import ConfirmDialog from "@/components/shared/dialogs/ConfirmDialog";
import ProductFormDialog from "@/components/shared/ProductFormDialog";
import {
  useProductList,
  useDeleteProduct,
  useProductPrices,
  useSyncProductPrice,
  useSyncProductHistory,
} from "@/hooks/useProduct";

export default function ProductsContent() {
  const addToast = useUIStore((state) => state.addToast);

  const { data, isLoading } = useProductList({ page_size: 100 });

  const deleteProduct = useDeleteProduct();

  const products = data?.items || [];

  // 创建/编辑共用 ProductFormDialog（issue #155 抽取）：editingProduct 为 null 即创建态
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);

  const handleEdit = (product: Product) => {
    setEditingProduct(product);
    setIsDialogOpen(true);
  };

  const handleDelete = (code: string, market?: string) => {
    setPendingDelete({ code, market });
  };
  
  const [pendingDelete, setPendingDelete] = useState<{ code: string; market?: string } | null>(null);

  const [priceDialogOpen, setPriceDialogOpen] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);

  const syncPrice = useSyncProductPrice();
  const syncHistory = useSyncProductHistory();

  const { data: priceData, isLoading: priceLoading } = useProductPrices(
    priceDialogOpen ? selectedProduct?.code : undefined,
    selectedProduct?.market,
    30
  );

  const handleSyncPrice = (product: Product) => {
    if (!product.market) {
      addToast({
        type: "error",
        title: "同步失败",
        message: "现金类产品无需同步价格",
      });
      return;
    }
    syncPrice.mutate({ code: product.code, market: product.market });
  };

  const handleSyncHistory = (product: Product) => {
    if (!product.market) {
      addToast({
        type: "error",
        title: "同步失败",
        message: "现金类产品无需同步历史",
      });
      return;
    }
    syncHistory.mutate({ code: product.code, market: product.market });
  };

  const handleViewPrices = (product: Product) => {
    setSelectedProduct(product);
    setPriceDialogOpen(true);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">产品管理</h1>
          <p className="text-muted-foreground">
            管理基金产品和数据源
          </p>
        </div>
        <ProductFormDialog
          open={isDialogOpen}
          onOpenChange={setIsDialogOpen}
          editingProduct={editingProduct}
          trigger={
            <Button onClick={() => setEditingProduct(null)}>
              <Plus className="mr-2 h-4 w-4" />
              添加产品
            </Button>
          }
        />
      </div>

      {/* 移动端入口：分类矩阵管理页（PC 端走侧边栏「分类」） */}
      <Link href="/m/asset-classifications" className="lg:hidden block">
        <Button variant="outline" size="sm" className="w-full">
          <Tags className="mr-2 h-4 w-4" />
          资产分类管理
        </Button>
      </Link>

      <Card>
        <CardHeader>
          <CardTitle>产品列表</CardTitle>
          <CardDescription>
            所有可投资的产品
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>代码</TableHead>
                <TableHead>市场</TableHead>
                <TableHead>名称</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>确认天数</TableHead>
                <TableHead>估值滞后</TableHead>
                <TableHead>QDII</TableHead>
                <TableHead>数据源</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {products.map((product) => (
                <TableRow key={`${product.code}-${product.market || "null"}`}>
                  <TableCell className="font-medium">{product.code}</TableCell>
                  <TableCell>{product.market || "-"}</TableCell>
                  <TableCell>{product.name}</TableCell>
                  <TableCell>{product.product_type}</TableCell>
                  <TableCell>{product.confirm_days}</TableCell>
                  {/* issue #228：快照估值取价日，0 显示 T，N 显示 T-N */}
                  <TableCell>
                    {(product.nav_lag_days ?? 0) > 0 ? `T-${product.nav_lag_days}` : "T"}
                  </TableCell>
                  <TableCell>{product.is_qdii ? "是" : "否"}</TableCell>
                  <TableCell>
                    {product.data_source_status === "success" ? (
                      <CheckCircle className="h-4 w-4 text-success" />
                    ) : product.data_source_status === "failed" ? (
                      <XCircle className="h-4 w-4 text-destructive" />
                    ) : (
                      <span className="text-warning">待验证</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleEdit(product)}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(product.code, product.market)}
                      disabled={deleteProduct.isPending}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                    {product.market && (
                      <>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleSyncPrice(product)}
                          disabled={syncPrice.isPending}
                        >
                          {syncPrice.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <RefreshCw className="h-4 w-4" />
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleSyncHistory(product)}
                          disabled={syncHistory.isPending}
                        >
                          {syncHistory.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <TrendingUp className="h-4 w-4" />
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleViewPrices(product)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {products.length === 0 && (
            <div className="text-center text-muted-foreground py-8">
              暂无产品
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={priceDialogOpen} onOpenChange={setPriceDialogOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>
              {selectedProduct?.name} ({selectedProduct?.code}) 价格走势
            </DialogTitle>
            <DialogDescription>
              最近 30 条价格记录
            </DialogDescription>
          </DialogHeader>
          {priceLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : priceData && priceData.length > 0 ? (
            <div className="rounded-md border max-h-96 overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>日期</TableHead>
                    <TableHead className="text-right">价格/净值</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {priceData.map((record) => (
                    <TableRow key={record.price_date}>
                      <TableCell>{record.price_date}</TableCell>
                      <TableCell className="text-right font-medium">
                        {formatNav(record.unit_price)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
              <TrendingUp className="h-8 w-8 mb-2" />
              <p>暂无价格数据，请先同步价格</p>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!pendingDelete}
        onOpenChange={(open) => !open && setPendingDelete(null)}
        title="删除产品"
        description="确定要删除该产品吗？已被持仓或交易引用的产品无法删除。"
        confirmText="删除"
        onConfirm={() => {
          if (pendingDelete) deleteProduct.mutate(pendingDelete);
          setPendingDelete(null);
        }}
      />
    </div>
  );
}
