# 安全扫描响应 Runbook

> 适用场景：定时或手动触发的 `security-scan.yml` 失败（红灯），以及 Dependabot 依赖升级/漏洞告警。

---

## 1. 响应时限

**Security Scan 红灯必须在下一个工作日内评估处置**——修复漏洞或在 issue 中记录豁免理由，不允许悬空。

## 2. 漏洞修复流程

- 漏洞修复与依赖升级一律走 `feature/` 分支 + PR，CI 全绿方可合入。
- 扫描豁免（如 `--ignore-vuln`）必须在 `security-scan.yml` 内注释记录理由与移除条件。

## 3. Dependabot 协同

- Dependabot（`.github/dependabot.yml`）每周自动提依赖升级 PR，与 weekly 扫描互补。
- Dependabot 漏洞告警（仓库设置项）开启后同样按 §1 时限响应。
