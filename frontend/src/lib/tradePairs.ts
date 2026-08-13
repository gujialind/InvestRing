import type { Trade } from "@/types/trade";

/**
 * 调仓列表结对视图行（#126 决策⑧）：
 * pair = 主行（基金腿 / 现金转移 sell 腿）+ 子行（配对现金腿 / 转移 buy 腿）；
 * single = 普通单行，或配对腿被筛选/分页排除后的孤儿回退。
 */
export type TradeRow =
  | { kind: "pair"; main: Trade; sub: Trade }
  | { kind: "single"; trade: Trade };

const CASH_CODE = "CASH";

/**
 * trades → 结对行。顺序敏感：分组与输出均保持传入顺序（= 后端
 * trade_date DESC, transfer_group, id DESC 排序序，决策⑪保证同组相邻）。
 *
 * 规则：
 * 1. 按 transfer_group 分组；
 * 2. `sub_` 前缀组（申赎配对现金腿）→ 恒 single，主体在申赎页；
 * 3. 组内恰 2 条且 1 条非 CASH + 1 条 CASH → pair（基金主、现金子）；
 * 4. 组内恰 2 条均 CASH → pair（sell 主、buy 子；现金跨平台转移）；
 * 5. 其余（孤儿单腿、异常多条）→ 全部 single 回退，不错行不空白。
 */
export function groupTradeRows(trades: Trade[]): TradeRow[] {
  const groups = new Map<string, Trade[]>();
  for (const t of trades) {
    // transfer_group 后端 NOT NULL；前端类型可选，缺省时按 id 自成一组走 single 回退
    const key = t.transfer_group ?? `__none_${t.id}`;
    const g = groups.get(key);
    if (g) g.push(t);
    else groups.set(key, [t]);
  }

  const rows: TradeRow[] = [];
  for (const [key, legs] of groups) {
    if (key.startsWith("sub_")) {
      legs.forEach((t) => rows.push({ kind: "single", trade: t }));
      continue;
    }
    if (legs.length === 2) {
      const [a, b] = legs;
      const fundLeg = a.product_code !== CASH_CODE ? a : b.product_code !== CASH_CODE ? b : null;
      const cashLeg = fundLeg === a ? b : fundLeg === b ? a : null;
      if (fundLeg && cashLeg) {
        rows.push({ kind: "pair", main: fundLeg, sub: cashLeg });
        continue;
      }
      if (a.product_code === CASH_CODE && b.product_code === CASH_CODE) {
        const sell = a.trade_type === "sell" ? a : b.trade_type === "sell" ? b : null;
        const buy = sell === a ? b : sell === b ? a : null;
        if (sell && buy) {
          rows.push({ kind: "pair", main: sell, sub: buy });
          continue;
        }
      }
    }
    legs.forEach((t) => rows.push({ kind: "single", trade: t }));
  }
  return rows;
}

/**
 * 现金子行派生数据（规范 §8）：主行为买入 → 现金扣款（-）；主行为卖出 → 现金到账（+）。
 * 符号为语义修饰，展示层手工前缀，不回写数值、不走涨跌色 token。
 */
export function cashSubMeta(main: Trade): { label: "现金扣款" | "现金到账"; sign: "-" | "+" } {
  return main.trade_type === "buy" ? { label: "现金扣款", sign: "-" } : { label: "现金到账", sign: "+" };
}

/**
 * CASH 孤儿单行的来源标注（§5.8 简化口径：由 transfer_group 前缀推导，不查 subscription、不新增接口）：
 * `sub_` 前缀 → 申赎确认；12 位 hex（现金转移组）被拆散的单腿 → 平台间转移；其余 → 调仓。
 */
export function cashOrphanLabel(trade: Trade): string {
  const g = trade.transfer_group ?? "";
  if (g.startsWith("sub_")) return "现金 · 申赎确认";
  if (/^[0-9a-f]{12}$/.test(g)) return "现金 · 平台间转移";
  return "现金 · 调仓";
}
