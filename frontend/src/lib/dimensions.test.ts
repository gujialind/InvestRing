import { describe, it, expect } from "vitest";
import {
  resolveSubDim,
  getDimensionOptions,
  clearInapplicableDims,
  SUB_DIM_BY_CLASS,
} from "@/lib/dimensions";
import type { AssetClassificationItem } from "@/types/asset-classification";

function item(over: Partial<AssetClassificationItem>): AssetClassificationItem {
  return {
    code: "X",
    dimension: "region",
    name: "x",
    sort_order: 1,
    is_active: true,
    applicable_asset_classes: [],
    ...over,
  };
}

describe("resolveSubDim", () => {
  it("组合级覆盖优先", () => {
    expect(resolveSubDim({ ASSET_STOCK: "style" }, "ASSET_STOCK")).toBe("style");
  });

  it("覆盖值为未知维度时回退内置默认（防御）", () => {
    expect(resolveSubDim({ ASSET_STOCK: "bogus" }, "ASSET_STOCK")).toBe("region");
  });

  it("无覆盖走内置默认；现金平铺；未知大类返回 null", () => {
    expect(resolveSubDim(null, "ASSET_STOCK")).toBe("region");
    expect(resolveSubDim(undefined, "ASSET_BOND")).toBe("segment");
    expect(resolveSubDim({}, "ASSET_CASH")).toBeNull();
    expect(resolveSubDim(null, "ASSET_UNKNOWN")).toBeNull();
  });

  it("内置默认表与文档口径一致（股票→地区、债券/商品→细分、现金平铺）", () => {
    expect(SUB_DIM_BY_CLASS).toEqual({
      ASSET_STOCK: "region",
      ASSET_BOND: "segment",
      ASSET_COMMODITY: "segment",
      ASSET_CASH: null,
    });
  });
});

describe("getDimensionOptions", () => {
  const dict = [
    item({ code: "ASSET_STOCK", dimension: "asset_class", name: "股票" }),
    item({ code: "REGION_CN", dimension: "region", name: "中国", applicable_asset_classes: ["ASSET_STOCK"] }),
    item({ code: "REGION_US", dimension: "region", name: "美国", applicable_asset_classes: ["ASSET_STOCK"] }),
    item({ code: "REGION_JP", dimension: "region", name: "日本", applicable_asset_classes: ["ASSET_BOND"] }),
    item({ code: "REGION_OFF", dimension: "region", name: "停用", is_active: false, applicable_asset_classes: ["ASSET_STOCK"] }),
  ];

  it("按维度过滤且排除停用值", () => {
    expect(getDimensionOptions(dict, "region").map((i) => i.code)).toEqual([
      "REGION_CN",
      "REGION_US",
      "REGION_JP",
    ]);
  });

  it("选了大类则按适用关系收窄", () => {
    expect(getDimensionOptions(dict, "region", "ASSET_STOCK").map((i) => i.code)).toEqual([
      "REGION_CN",
      "REGION_US",
    ]);
    expect(getDimensionOptions(dict, "region", "ASSET_BOND").map((i) => i.code)).toEqual([
      "REGION_JP",
    ]);
  });

  it("asset_class 维度入口：不传大类即启用大类列表", () => {
    expect(getDimensionOptions(dict, "asset_class").map((i) => i.code)).toEqual(["ASSET_STOCK"]);
  });
});

describe("clearInapplicableDims", () => {
  const dict = [
    item({ code: "REGION_CN", dimension: "region", applicable_asset_classes: ["ASSET_STOCK"] }),
    item({ code: "STYLE_GROWTH", dimension: "style", applicable_asset_classes: ["ASSET_BOND"] }),
    item({ code: "STYLE_OFF", dimension: "style", is_active: false, applicable_asset_classes: ["ASSET_STOCK"] }),
  ];

  it("不再适用新大类的维度值清空，适用的保留", () => {
    const next = clearInapplicableDims(
      { asset_class: undefined, region: "REGION_CN", style: "STYLE_GROWTH" },
      "ASSET_STOCK",
      dict
    );
    expect(next).toEqual({ asset_class: "ASSET_STOCK", region: "REGION_CN", style: undefined });
  });

  it("停用值视为不适用", () => {
    const next = clearInapplicableDims({ style: "STYLE_OFF" }, "ASSET_STOCK", dict);
    expect(next.style).toBeUndefined();
  });

  it("未选大类时仅更新 asset_class，其余维度不动", () => {
    const next = clearInapplicableDims({ region: "REGION_CN" }, undefined, dict);
    expect(next).toEqual({ asset_class: undefined, region: "REGION_CN" });
  });
});
