"use client";

import MainLayout from "@/components/layout/MainLayout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Play, Pause, RotateCcw, Loader2 } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { taskApi } from "@/lib/api";
import { useUIStore } from "@/stores/uiStore";
import { formatDate } from "@/lib/utils";

export default function TasksPage() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);

  const { data: tasksData, isLoading } = useQuery({
    queryKey: ["tasks", "list"],
    queryFn: () => taskApi.list(),
    staleTime: 10 * 1000,
  });

  const tasks = ((tasksData as any)?.items) as any[] || [];

  const runTask = useMutation({
    mutationFn: (code: string) => taskApi.run(code),
    onSuccess: (_, code) => {
      addToast({ type: "success", title: "任务已启动", message: `任务 ${code} 已启动` });
    },
    onError: (error: any) => {
      addToast({ type: "error", title: "启动失败", message: error.message || "请稍后重试" });
    },
  });

  const enableTask = useMutation({
    mutationFn: (code: string) => taskApi.enable(code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks", "list"] });
      addToast({ type: "success", title: "启用成功", message: "任务已启用" });
    },
    onError: (error: any) => {
      addToast({ type: "error", title: "操作失败", message: error.message || "请稍后重试" });
    },
  });

  const disableTask = useMutation({
    mutationFn: (code: string) => taskApi.disable(code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks", "list"] });
      addToast({ type: "success", title: "禁用成功", message: "任务已禁用" });
    },
    onError: (error: any) => {
      addToast({ type: "error", title: "操作失败", message: error.message || "请稍后重试" });
    },
  });

  const handleToggle = (code: string, isEnabled: boolean) => {
    if (isEnabled) {
      disableTask.mutate(code);
    } else {
      enableTask.mutate(code);
    }
  };

  const handleRun = (code: string) => {
    if (confirm(`确定要手动执行任务: ${code} 吗？`)) {
      runTask.mutate(code);
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
        <div>
          <h1 className="text-3xl font-bold tracking-tight">任务管理</h1>
          <p className="text-muted-foreground">
            管理定时任务和手动触发
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>定时任务</CardTitle>
            <CardDescription>
              系统定时任务列表
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>任务名称</TableHead>
                  <TableHead>描述</TableHead>
                  <TableHead>Cron表达式</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>上次执行</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tasks?.map((task: any) => (
                  <TableRow key={task.id}>
                    <TableCell className="font-medium">{task.name}</TableCell>
                    <TableCell>{task.description || "--"}</TableCell>
                    <TableCell>
                      <code className="rounded bg-muted px-2 py-1 text-sm">
                        {task.cron_expression}
                      </code>
                    </TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        task.is_enabled
                          ? "bg-green-100 text-green-800"
                          : "bg-gray-100 text-gray-800"
                      }`}>
                        {task.is_enabled ? "启用" : "禁用"}
                      </span>
                    </TableCell>
                    <TableCell>{task.last_run_at ? formatDate(task.last_run_at) : "从未执行"}</TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleRun(task.code)}
                        disabled={runTask.isPending}
                      >
                        <RotateCcw className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleToggle(task.code, task.is_enabled)}
                        disabled={enableTask.isPending || disableTask.isPending}
                      >
                        {task.is_enabled ? (
                          <Pause className="h-4 w-4" />
                        ) : (
                          <Play className="h-4 w-4" />
                        )}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {tasks.length === 0 && (
              <div className="text-center text-muted-foreground py-8">
                暂无定时任务
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}
