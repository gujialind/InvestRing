"use client";

import { Button } from "@/components/ui/button";
import { Power, PowerOff, Plus, ArrowRightLeft, RefreshCw } from "lucide-react";
import Link from "next/link";

interface PortfolioActionButtonsProps {
  portfolioCode: string;
  status: "draft" | "active" | "closed";
  /** 链接前缀，如 "/portfolio" 或 "/m/portfolio" */
  basePath: string;
  /** desktop: 行内按钮；mobile: 2 列网格 */
  variant?: "desktop" | "mobile";
  onCloseClick: () => void;
  onActivateClick: () => void;
  isClosePending?: boolean;
  isActivatePending?: boolean;
}

/**
 * 组合详情页操作按钮组（草稿/活跃/关闭三态）。
 * 业务逻辑两端一致，仅布局与链接前缀通过 variant / basePath 区分。
 * 注：后端不提供删除组合能力（外键 RESTRICT，生命周期由关闭/重新激活管理），故无删除入口。
 */
export default function PortfolioActionButtons({
  portfolioCode,
  status,
  basePath,
  variant = "desktop",
  onCloseClick,
  onActivateClick,
  isClosePending,
  isActivatePending,
}: PortfolioActionButtonsProps) {
  const cls = variant === "mobile" ? "w-full" : "";

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
          <>
            <Link href={`${basePath}/${portfolioCode}/share-change-events`}>
              <Button variant="outline">
                <RefreshCw className="mr-2 h-4 w-4" />
                份额变动
              </Button>
            </Link>
            <Button variant="outline" onClick={onCloseClick} disabled={isClosePending}>
              <PowerOff className="mr-2 h-4 w-4 text-red-500" />
              关闭组合
            </Button>
          </>
        )}
      </div>
    );
  }

  // closed
  return (
    <Button
      variant="outline"
      onClick={onActivateClick}
      disabled={isActivatePending}
      className={variant === "mobile" ? "col-span-2 w-full" : ""}
    >
      <Power className="mr-2 h-4 w-4 text-green-500" />
      重新激活
    </Button>
  );
}
