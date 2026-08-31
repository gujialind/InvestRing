"use client";

import { Button } from "@/components/ui/button";
import { Power, Plus, ArrowRightLeft, RefreshCw, Camera } from "lucide-react";
import Link from "next/link";

interface PortfolioActionButtonsProps {
  portfolioCode: string;
  status: "draft" | "active" | "closed";
  /** 链接前缀，如 "/portfolio" 或 "/m/portfolio" */
  basePath: string;
  /** desktop: 行内按钮；mobile: 仅申赎+调仓（2 列网格由调用方容器控制） */
  variant?: "desktop" | "mobile";
  onActivateClick: () => void;
  isActivatePending?: boolean;
}

/**
 * 组合详情页操作按钮组（草稿/活跃/关闭三态，issue #99）。
 * 详情页不再提供「关闭组合」入口（关闭仅在列表页）；业务逻辑两端一致，
 * 仅布局与链接前缀通过 variant / basePath 区分。
 * 注：后端不提供删除组合能力（外键 RESTRICT，生命周期由关闭/重新激活管理），故无删除入口。
 */
export default function PortfolioActionButtons({
  portfolioCode,
  status,
  basePath,
  variant = "desktop",
  onActivateClick,
  isActivatePending,
}: PortfolioActionButtonsProps) {
  const cls = variant === "mobile" ? "w-full" : "";

  // 快照管理入口仅 desktop 渲染（移动端在页尾「管理」列表，#351）
  const snapshotEntry = variant === "desktop" ? (
    <Link href={`${basePath}/${portfolioCode}/snapshots`}>
      <Button variant="outline">
        <Camera className="mr-2 h-4 w-4" />
        快照管理
      </Button>
    </Link>
  ) : null;

  if (status === "draft") {
    return (
      <div className={variant === "mobile" ? "grid grid-cols-2 gap-2" : "flex gap-2"}>
        <Link href={`${basePath}/${portfolioCode}/subscriptions`}>
          <Button className={cls}>
            <Plus className="mr-2 h-4 w-4" />
            {variant === "mobile" ? "首次申购" : "首次申购激活"}
          </Button>
        </Link>
      </div>
    );
  }

  if (status === "active") {
    return (
      <div className={variant === "mobile" ? "grid grid-cols-2 gap-2" : "flex gap-2"}>
        <Link href={`${basePath}/${portfolioCode}/subscriptions`}>
          <Button className={cls}>
            <Plus className="mr-2 h-4 w-4" />
            申购赎回
          </Button>
        </Link>
        <Link href={`${basePath}/${portfolioCode}/trades`}>
          <Button variant="outline" className={cls}>
            <ArrowRightLeft className="mr-2 h-4 w-4" />
            {variant === "mobile" ? "调仓" : "调仓交易"}
          </Button>
        </Link>
        {variant === "desktop" && (
          <Link href={`${basePath}/${portfolioCode}/share-change-events`}>
            <Button variant="outline">
              <RefreshCw className="mr-2 h-4 w-4" />
              份额变动
            </Button>
          </Link>
        )}
        {snapshotEntry}
      </div>
    );
  }

  // closed
  return (
    <>
      <Button
        variant="outline"
        onClick={onActivateClick}
        disabled={isActivatePending}
        className={variant === "mobile" ? "col-span-2 w-full" : ""}
      >
        <Power className="mr-2 h-4 w-4 text-success" />
        重新激活
      </Button>
      {snapshotEntry}
    </>
  );
}
