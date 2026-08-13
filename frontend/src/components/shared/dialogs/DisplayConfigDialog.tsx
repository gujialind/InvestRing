"use client";

import { useEffect, useState } from "react";
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
import { SUB_DIM_BY_CLASS } from "@/components/shared/PositionSections";

/** 维度英文键 → 中文标签（配置下拉展示用） */
const DIM_LABELS: Record<string, string> = {
  region: "地域",
  style: "风格",
  size: "规模",
  segment: "细分",
};

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
 */
export default function DisplayConfigDialog({
  open,
  onOpenChange,
  portfolioCode,
  currentConfig,
}: DisplayConfigDialogProps) {
  const { data: dictData } = useAssetClassifications();
  const updatePortfolio = useUpdatePortfolio(portfolioCode);

  // 可配置大类：字典中 asset_class 维度值且在规则矩阵中有行（sort_order 排序）
  const configurableClasses = (dictData?.items ?? [])
    .filter(
      (i) =>
        i.dimension === "asset_class" &&
        Object.keys(dictData?.dimension_rules?.[i.code] ?? {}).length > 0
    )
    .sort((a, b) => a.sort_order - b.sort_order);

  // 各大类当前选择：维度键或 DEFAULT_VALUE；打开时从既有配置回填
  const [selections, setSelections] = useState<Record<string, string>>({});
  useEffect(() => {
    if (!open) return;
    const init: Record<string, string> = {};
    for (const cls of configurableClasses) {
      init[cls.code] = currentConfig?.[cls.code] ?? DEFAULT_VALUE;
    }
    setSelections(init);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

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
              ? `默认（${DIM_LABELS[defaultDim] ?? defaultDim}）`
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
                    {ruleDims
                      .filter((d) => d !== defaultDim)
                      .map((d) => (
                        <SelectItem key={d} value={d}>
                          {DIM_LABELS[d] ?? d}
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
