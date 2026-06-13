"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import MainLayout from "@/components/layout/MainLayout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { format } from "date-fns";
import { zhCN } from "date-fns/locale";
import { Calendar as CalendarIcon, Loader2, RefreshCw, CheckCircle2, XCircle, AlertTriangle, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  useSnapshotStatus,
  useGenerateSnapshot,
  useRecalculateSnapshots,
  useValidateSnapshot,
  useDeleteSnapshot,
} from "@/hooks/useSnapshot";
import type { SnapshotValidationCheck } from "@/lib/api";

export default function PortfolioSnapshotsPage() {
  const params = useParams();
  const portfolioCode = params.code as string;

  // 查询状态
  const { data: statusData, isLoading: statusLoading } = useSnapshotStatus(portfolioCode);

  // Mutations
  const generateSnapshot = useGenerateSnapshot();
  const recalculateSnapshots = useRecalculateSnapshots();
  const validateSnapshot = useValidateSnapshot();
  const deleteSnapshot = useDeleteSnapshot();

  // 单日生成状态
  const [singleDate, setSingleDate] = useState<Date>();
  const [showSingleDialog, setShowSingleDialog] = useState(false);
  const [validationResult, setValidationResult] = useState<SnapshotValidationCheck[] | null>(null);

  // 区间重算状态
  const [startDate, setStartDate] = useState<Date>();
  const [endDate, setEndDate] = useState<Date>();
  const [showRecalcDialog, setShowRecalcDialog] = useState(false);
  const [forceRecalc, setForceRecalc] = useState(false);

  // 快速更新状态
  const [quickUpdateLoading, setQuickUpdateLoading] = useState(false);

  // 快速更新：基于今天生成最新快照
  const handleQuickUpdate = async () => {
    const today = new Date();
    const dateStr = format(today, "yyyy-MM-dd");
    
    setQuickUpdateLoading(true);
    try {
      await generateSnapshot.mutateAsync({
        portfolioCode,
        targetDate: dateStr,
      });
    } catch (error) {
      console.error("快速更新失败:", error);
    } finally {
      setQuickUpdateLoading(false);
    }
  };

  // 预检单日快照
  const handleValidateSingle = async () => {
    if (!singleDate) return;
    
    const dateStr = format(singleDate, "yyyy-MM-dd");
    try {
      const result = await validateSnapshot.mutateAsync({
        portfolioCode,
        targetDate: dateStr,
      });
      setValidationResult(result.checks);
    } catch (error) {
      console.error("验证失败:", error);
    }
  };

  // 生成单日快照
  const handleGenerateSingle = async () => {
    if (!singleDate) return;
    
    const dateStr = format(singleDate, "yyyy-MM-dd");
    await generateSnapshot.mutateAsync({
      portfolioCode,
      targetDate: dateStr,
    });
    setShowSingleDialog(false);
    setValidationResult(null);
  };

  // 区间重算
  const handleRecalculate = async () => {
    if (!startDate || !endDate) return;
    
    await recalculateSnapshots.mutateAsync({
      portfolioCode,
      startDate: format(startDate, "yyyy-MM-dd"),
      endDate: format(endDate, "yyyy-MM-dd"),
      force: forceRecalc,
    });
    setShowRecalcDialog(false);
  };

  // 删除指定日期快照
  const handleDelete = async (date: string) => {
    if (!confirm(`确定要删除 ${date} 的快照吗？`)) return;
    
    await deleteSnapshot.mutateAsync({
      portfolioCode,
      snapshotDate: date,
    });
  };

  if (statusLoading) {
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
      <div className="container mx-auto px-4 py-6">
        <div className="mb-6">
          <h1 className="text-3xl font-bold">快照管理</h1>
          <p className="text-muted-foreground mt-1">
            管理组合历史快照数据，支持手动生成和区间重算
          </p>
        </div>

        {/* 快照状态概览 */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>快照状态</CardTitle>
            <CardDescription>组合快照数据统计</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 border rounded-lg">
                <div className="text-sm text-muted-foreground">最新快照日期</div>
                <div className="text-2xl font-bold mt-1">
                  {statusData?.latest_snapshot_date || "无"}
                </div>
              </div>
              <div className="p-4 border rounded-lg">
                <div className="text-sm text-muted-foreground">快照总数</div>
                <div className="text-2xl font-bold mt-1">
                  {statusData?.total_snapshots || 0}
                </div>
              </div>
              <div className="p-4 border rounded-lg">
                <div className="text-sm text-muted-foreground">最早快照日期</div>
                <div className="text-2xl font-bold mt-1">
                  {statusData?.first_snapshot_date || "无"}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 操作按钮 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">快速更新</CardTitle>
              <CardDescription>基于今天生成最新快照</CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                onClick={handleQuickUpdate}
                className="w-full"
                variant="default"
                disabled={generateSnapshot.isPending || quickUpdateLoading}
              >
                {quickUpdateLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    更新中...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="mr-2 h-4 w-4" />
                    立即更新
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">单日生成</CardTitle>
              <CardDescription>为指定日期生成快照</CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                onClick={() => setShowSingleDialog(true)}
                className="w-full"
                variant="outline"
                disabled={generateSnapshot.isPending}
              >
                {generateSnapshot.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    生成中...
                  </>
                ) : (
                  <>
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    选择日期生成
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">区间重算</CardTitle>
              <CardDescription>重新计算指定时间区间的快照</CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                onClick={() => setShowRecalcDialog(true)}
                variant="outline"
                className="w-full"
                disabled={recalculateSnapshots.isPending}
              >
                {recalculateSnapshots.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    重算中...
                  </>
                ) : (
                  <>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    选择区间重算
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* 历史快照列表 */}
        {statusData?.missing_dates && statusData.missing_dates.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>缺失的快照日期</CardTitle>
              <CardDescription>以下交易日缺少快照数据</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {statusData.missing_dates.slice(0, 20).map((date) => (
                  <Badge key={date} variant="destructive">
                    {date}
                  </Badge>
                ))}
                {statusData.missing_dates.length > 20 && (
                  <Badge variant="secondary">
                    +{statusData.missing_dates.length - 20} 更多
                  </Badge>
                )}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* 单日生成对话框 */}
      <Dialog open={showSingleDialog} onOpenChange={setShowSingleDialog}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>生成单日快照</DialogTitle>
            <DialogDescription>
              选择要生成快照的日期，系统将自动校验依赖数据
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>目标日期</Label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className={cn(
                      "w-full justify-start text-left font-normal",
                      !singleDate && "text-muted-foreground"
                    )}
                  >
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {singleDate ? format(singleDate, "yyyy-MM-dd") : "选择日期"}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0">
                  <Calendar
                    mode="single"
                    selected={singleDate}
                    onSelect={setSingleDate}
                    locale={zhCN}
                  />
                </PopoverContent>
              </Popover>
            </div>

            {validationResult && (
              <div className="space-y-2">
                <Label>校验结果</Label>
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {validationResult.map((check, idx) => (
                    <Alert
                      key={idx}
                      variant={
                        check.status === "failed"
                          ? "destructive"
                          : check.status === "warning"
                          ? "default"
                          : "default"
                      }
                      className={cn(
                        check.status === "passed" && "border-green-500 bg-green-50",
                        check.status === "warning" && "border-yellow-500 bg-yellow-50"
                      )}
                    >
                      {check.status === "passed" && (
                        <CheckCircle2 className="h-4 w-4 text-green-600" />
                      )}
                      {check.status === "failed" && (
                        <XCircle className="h-4 w-4" />
                      )}
                      {check.status === "warning" && (
                        <AlertTriangle className="h-4 w-4 text-yellow-600" />
                      )}
                      <AlertDescription>
                        <span className="font-medium">{check.check_type}</span>
                        <span className="ml-2">{check.message}</span>
                      </AlertDescription>
                    </Alert>
                  ))}
                </div>
              </div>
            )}
          </div>

          <DialogFooter>
            {!validationResult ? (
              <Button
                onClick={handleValidateSingle}
                disabled={!singleDate || validateSnapshot.isPending}
              >
                {validateSnapshot.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    校验中...
                  </>
                ) : (
                  "预检验证"
                )}
              </Button>
            ) : (
              <>
                <Button variant="outline" onClick={() => setValidationResult(null)}>
                  返回
                </Button>
                <Button
                  onClick={handleGenerateSingle}
                  disabled={
                    validationResult.some((c) => c.status === "failed") ||
                    generateSnapshot.isPending
                  }
                >
                  {generateSnapshot.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      生成中...
                    </>
                  ) : (
                    "确认生成"
                  )}
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 区间重算对话框 */}
      <Dialog open={showRecalcDialog} onOpenChange={setShowRecalcDialog}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>区间重算快照</DialogTitle>
            <DialogDescription>
              重新计算指定时间区间内的所有快照（将删除旧快照并重新生成）
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>起始日期</Label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className={cn(
                      "w-full justify-start text-left font-normal",
                      !startDate && "text-muted-foreground"
                    )}
                  >
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {startDate ? format(startDate, "yyyy-MM-dd") : "选择起始日期"}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0">
                  <Calendar
                    mode="single"
                    selected={startDate}
                    onSelect={setStartDate}
                    locale={zhCN}
                  />
                </PopoverContent>
              </Popover>
            </div>

            <div className="space-y-2">
              <Label>结束日期</Label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className={cn(
                      "w-full justify-start text-left font-normal",
                      !endDate && "text-muted-foreground"
                    )}
                  >
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {endDate ? format(endDate, "yyyy-MM-dd") : "选择结束日期"}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0">
                  <Calendar
                    mode="single"
                    selected={endDate}
                    onSelect={setEndDate}
                    locale={zhCN}
                  />
                </PopoverContent>
              </Popover>
            </div>

            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="force"
                checked={forceRecalc}
                onChange={(e) => setForceRecalc(e.target.checked)}
                className="h-4 w-4 rounded border-gray-300"
              />
              <Label htmlFor="force" className="text-sm">
                强制重算（跳过依赖数据校验）
              </Label>
            </div>

            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                重算将删除指定区间内的所有快照并重新生成，此操作不可撤销。
                请确保净值数据、交易数据等已完整同步。
              </AlertDescription>
            </Alert>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRecalcDialog(false)}>
              取消
            </Button>
            <Button
              onClick={handleRecalculate}
              disabled={
                !startDate ||
                !endDate ||
                recalculateSnapshots.isPending
              }
              variant="destructive"
            >
              {recalculateSnapshots.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  重算中...
                </>
              ) : (
                <>
                  <Trash2 className="mr-2 h-4 w-4" />
                  开始重算
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </MainLayout>
  );
}
