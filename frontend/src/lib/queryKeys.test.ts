import { describe, it, expect } from "vitest";
import { queryKeys } from "@/lib/queryKeys";

// #344 防回归：mutation 失效键必须是列表键的真前缀，否则
// invalidateQueries 逐元素匹配失配、列表不刷新
describe("queryKeys.shareChangeEvents", () => {
  it("byPortfolio 是任意 list 键的真前缀", () => {
    const prefix = queryKeys.shareChangeEvents.byPortfolio("P1");
    expect(prefix).toEqual(["share-change-events", "P1"]);

    const listKey = queryKeys.shareChangeEvents.list("P1", { page: 1, page_size: 20 });
    expect(listKey.slice(0, prefix.length)).toEqual(prefix);
  });

  it("list(code) 少传 params 产生尾 undefined 键，并非真前缀（失效失配根因）", () => {
    const shorthand = queryKeys.shareChangeEvents.list("P1");
    expect(shorthand).toEqual(["share-change-events", "P1", undefined]);

    const listKey = queryKeys.shareChangeEvents.list("P1", { page: 1 });
    expect(listKey.slice(0, shorthand.length)).not.toEqual(shorthand);
  });
});
