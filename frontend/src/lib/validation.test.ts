import { describe, it, expect } from "vitest";
import { validatePlatformCode, parsePositiveNumber } from "@/lib/validation";

describe("validatePlatformCode", () => {
  it("空平台返回错误文案", () => {
    expect(validatePlatformCode("")).toBe("请选择平台");
  });

  it("已选平台通过", () => {
    expect(validatePlatformCode("ALIPAY")).toBeNull();
  });
});

describe("parsePositiveNumber", () => {
  it("正数解析通过", () => {
    expect(parsePositiveNumber("100")).toBe(100);
    expect(parsePositiveNumber("0.01")).toBe(0.01);
    expect(parsePositiveNumber("1e3")).toBe(1000);
  });

  it("零、负数、非法输入拦截", () => {
    expect(parsePositiveNumber("0")).toBeNull();
    expect(parsePositiveNumber("-5")).toBeNull();
    expect(parsePositiveNumber("abc")).toBeNull();
    expect(parsePositiveNumber("")).toBeNull();
    expect(parsePositiveNumber("NaN")).toBeNull();
    expect(parsePositiveNumber("Infinity")).toBeNull();
  });

  it("parseFloat 前缀语义：尾随垃圾按前缀解析（与组件原行为一致）", () => {
    expect(parsePositiveNumber("10abc")).toBe(10);
  });
});
