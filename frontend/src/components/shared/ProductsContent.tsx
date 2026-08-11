"use client";

import { useState } from "react";
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Plus, Pencil, Trash2, CheckCircle, XCircle, Loader2, RefreshCw, TrendingUp, Eye } from "lucide-react";
import { Product, ProductCreate } from "@/types/product";
import { useUIStore } from "@/stores/uiStore";
import { formatNav } from "@/lib/utils";
import ConfirmDialog from "@/components/shared/dialogs/ConfirmDialog";
import {
  useProductList,
  useCreateProduct,
  useUpdateProduct,
  useDeleteProduct,
  useProductPrices,
  useSyncProductPrice,
  useSyncProductHistory,
} from "@/hooks/useProduct";

export default function ProductsContent() {
  const addToast = useUIStore((state) => state.addToast);

  const { data, isLoading } = useProductList({ page_size: 100 });

  const createProduct = useCreateProduct();
  const updateProduct = useUpdateProduct();
  const deleteProduct = useDeleteProduct();

  const products = data?.items || [];

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [formData, setFormData] = useState<Partial<Product>>({
    code: "",
    market: "",
    name: "",
    product_type: "ETF",
    confirm_days: 1,
    is_qdii: false,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (editingProduct) {
      updateProduct.mutate(
        {
          code: editingProduct.code,
          market: editingProduct.market,
          data: {
            name: formData.name,
            asset_class_code: formData.asset_class_code,
            confirm_days: formData.confirm_days,
            is_qdii: formData.is_qdii,
          },
        },
        {
          onSuccess: () => {
            setIsDialogOpen(false);
            setEditingProduct(null);
            resetForm();
          },
        }
      );
    } else {
      createProduct.mutate(formData as ProductCreate, {
        onSuccess: () => {
          setIsDialogOpen(false);
          resetForm();
        },
      });
    }
  };

  const resetForm = () => {
    setFormData({ code: "", market: "", name: "", product_type: "ETF", confirm_days: 1, is_qdii: false });
  };

  const handleEdit = (product: Product) => {
    setEditingProduct(product);
    setFormData(product);
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
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={() => {
              setEditingProduct(null);
              resetForm();
            }}>
              <Plus className="mr-2 h-4 w-4" />
              添加产品
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{editingProduct ? "编辑产品" : "添加产品"}</DialogTitle>
              <DialogDescription>
                {editingProduct ? "修改产品信息" : "创建新的产品"}
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmit}>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label htmlFor="code">产品代码</Label>
                  <Input
                    id="code"
                    value={formData.code}
                    onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                    disabled={!!editingProduct}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="market">市场</Label>
                  <select
                    id="market"
                    value={formData.market}
                    onChange={(e) => setFormData({ ...formData, market: e.target.value })}
                    disabled={!!editingProduct}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <option value="">无（现金类）</option>
                    <option value="CN_EXCHANGE">A股场内</option>
                    <option value="CN_OTC">内地场外</option>
                    <option value="HK_MUTUAL">香港互认</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="name">产品名称</Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="product_type">产品类型</Label>
                  <select
                    id="product_type"
                    value={formData.product_type}
                    onChange={(e) => setFormData({ ...formData, product_type: e.target.value })}
                    disabled={!!editingProduct}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <option value="ETF">ETF</option>
                    <option value="OEF">开放式基金</option>
                    <option value="LOF">LOF</option>
                    <option value="CASH">现金</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="confirm_days">确认天数</Label>
                  <Input
                    id="confirm_days"
                    type="number"
                    value={formData.confirm_days}
                    onChange={(e) => setFormData({ ...formData, confirm_days: parseInt(e.target.value) })}
                    required
                  />
                </div>
                <div className="flex items-center gap-2">
                  <input
                    id="is_qdii"
                    type="checkbox"
                    checked={formData.is_qdii}
                    onChange={(e) => setFormData({ ...formData, is_qdii: e.target.checked })}
                    className="h-4 w-4 rounded border-gray-300"
                  />
                  <Label htmlFor="is_qdii">QDII基金</Label>
                </div>
              </div>
              <DialogFooter>
                <Button type="submit" disabled={createProduct.isPending || updateProduct.isPending}>
                  {(createProduct.isPending || updateProduct.isPending) && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  {editingProduct ? "保存修改" : "创建产品"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

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
