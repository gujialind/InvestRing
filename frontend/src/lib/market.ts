import { formatMarketName } from "@/lib/utils";

/**
 * 市场筛选选项（#324 抽取共享）：产品筛选弹窗 / 产品管理页 / 提交交易产品选择器
 * 三处共用，label 经 formatMarketName 与产品表单下拉保持一致。
 */
export const MARKET_OPTIONS = ["CN_EXCHANGE", "CN_OTC", "HK_MUTUAL"].map((v) => ({
  value: v,
  label: formatMarketName(v),
}));
