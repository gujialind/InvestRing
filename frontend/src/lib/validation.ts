/**
 * 申购/赎回表单校验纯函数（issue #253：自 SubscriptionsContent 抽取，行为不变）。
 * 校验规则与后端约束的对应关系见各函数注释。
 */

/**
 * 平台必选校验：返回错误文案，通过返回 null。
 * 原生 <select required> 替换为自定义组件后浏览器校验失效，须手动拦截。
 */
export function validatePlatformCode(platformCode: string): string | null {
  return platformCode ? null : "请选择平台";
}

/**
 * 正有限数解析（编辑表单在原生 required/min 之外的双保险）：
 * 非法数值或非正数返回 null，通过返回数值本身。
 */
export function parsePositiveNumber(raw: string): number | null {
  const n = parseFloat(raw);
  return Number.isFinite(n) && n > 0 ? n : null;
}
