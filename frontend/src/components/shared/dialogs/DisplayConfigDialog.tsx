"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2 } from "lucide-react";
import { useAssetClassifications } from "@/hooks/useAssetClassification";
import { useUpdatePortfolio } from "@/hooks/usePortfolio";
import { DIMENSION_LABELS, SUB_DIM_BY_CLASS } from "@/lib/dimensions";

/** Select 中「默认」选项的哨兵值（Radix Select 不允许空字符串 value） */
const DEFAULT_VALUE = "__default__";

interface DisplayConfigDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  portfolioCode: string;
  /** 组合当前 display_config（null/缺省 = 未配置） */
  currentConfig?: Record<string, string> | null;
}

/**
 * 持仓明细二级分组维度配置弹窗（issue #144，双端共用）。
 * 枚举维度规则矩阵中有行的全部大类（不限当前持仓，支持预配置；
 * 现金大类无规则行天然不出现），可选维度以 asset_class_dimension_rule
 * 登记为准（required/optional 均可）。保存仅提交显式覆盖项，
 * 全部默认时传 null 清空配置。
 *
 * 字典查询与详情页同 key（"asset_class"，顶层 dimension_rules 不受
 * 维度过滤影响），复用页面缓存且被页面 loading 闸门覆盖，打开弹窗时
 * 字典必然就绪，不存在初始化竞态。
 */
export default function DisplayConfigDialog({
  open,
  onOpenChange,
  portfolioCode,
  currentConfig,
}: DisplayConfigDialogProps) {
  const { data: dictData } = useAssetClassifications("asset_class");
  const updatePortfolio = useUpdatePortfolio(portfolioCode);

  // 可配置大类：字典中 asset_class 维度值且在规则矩阵中有行（sort_order 排序）；
  // useMemo 稳定引用，供下方初始化 effect 依赖
  const configurableClasses = useMemo(
    () =>
      (dictData?.items ?? [])
        .filter(
          (i) =>
            i.dimension === "asset_class" &&
            Object.keys(dictData?.dimension_rules?.[i.code] ?? {}).length > 0
        )
        .sort((a, b) => a.sort_order - b.sort_order),
    [dictData]
  );

  // 各大类当前选择：维度键或 DEFAULT_VALUE；打开时从既有配置回填，
  // 依赖 configurableClasses/currentConfig——字典晚到（缓存未命中）时
  // 数据到达后重跑初始化，避免 selections 停留在空状态导致保存误清空配置
  const [selections, setSelections] = useState<Record<string, string>>({});
  useEffect(() => {
    if (!open) return;
    const init: Record<string, string> = {};
    for (const cls of configurableClasses) {
      init[cls.code] = currentConfig?.[cls.code] ?? DEFAULT_VALUE;
    }
    setSelections(init);
  }, [open, configurableClasses, currentConfig]);

  const handleSave = () => {
    const overrides: Record<string, string> = {};
    for (const cls of configurableClasses) {
      const value = selections[cls.code] ?? DEFAULT_VALUE;
      if (value !== DEFAULT_VALUE) {
        overrides[cls.code] = value;
      }
    }
    updatePortfolio.mutate(
      { display_config: Object.keys(overrides).length ? overrides : null },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>分组维度</DialogTitle>
          <DialogDescription>
            为各大类设置持仓明细的二级分组维度；选「默认」的大类按内置维度分组。
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          {configurableClasses.map((cls) => {
            const defaultDim = SUB_DIM_BY_CLASS[cls.code] ?? null;
            const defaultLabel = defaultDim
              ? `默认（${DIMENSION_LABELS[defaultDim] ?? defaultDim}）`
              : "默认（平铺）";
            const ruleDims = Object.keys(
              dictData?.dimension_rules?.[cls.code] ?? {}
            );
            return (
              <div key={cls.code} className="flex items-center justify-between gap-4">
                <span className="text-sm">{cls.name}</span>
                <Select
                  value={selections[cls.code] ?? DEFAULT_VALUE}
                  onValueChange={(v) =>
                    setSelections((prev) => ({ ...prev, [cls.code]: v }))
                  }
                >
                  <SelectTrigger className="w-40">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={DEFAULT_VALUE}>{defaultLabel}</SelectItem>
                    {/* 不剔除 defaultDim：显式覆盖值等于内置默认维度时（CLI/API 可
                        合法落库）需有匹配选项，否则触发器渲染空白 */}
                    {ruleDims.map((d) => (
                      <SelectItem key={d} value={d}>
                        {DIMENSION_LABELS[d] ?? d}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            );
          })}
          {configurableClasses.length === 0 && (
            <p className="text-sm text-muted-foreground">暂无可配置的大类</p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button
            onClick={handleSave}
            disabled={updatePortfolio.isPending || configurableClasses.length === 0}
          >
            {updatePortfolio.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
