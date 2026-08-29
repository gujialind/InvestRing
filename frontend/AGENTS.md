# frontend/AGENTS.md — 前端模块操作指南

> 双端路由/Middleware 约定与组件复用三层模型见根 `AGENTS.md` §5；视觉规范（语义色/涨跌色/图表色/数字格式）见 `docs/design/visual-spec.md`——**写前端代码前必读**。本文件只写怎么跑、怎么验。

## 质量门禁

```bash
../scripts/verify-frontend.sh        # 推送前本地门禁（与 CI frontend-check 同口径）
../scripts/verify-frontend.sh --quick  # 跳过 build
```

等价于 `npm run lint` + `npx tsc --noEmit` + `npm run build`；构建期强制 0 error。

## E2E（Playwright）

```bash
python3 backend/scripts/run_e2e_backend.py   # 1. 起本地后端（自动种子，监听 :8000）
cd frontend && npm run build \
  && cp -r .next/static .next/standalone/.next/static \
  && cp -r public .next/standalone/public    # 2. 生产构建 + 组装 standalone
npm run test:e2e                             # 3. 跑测试
```

- **本地默认只跑影响面 spec，全量由 CI 兜底**（`frontend-e2e` job 合入前强制跑全套）：`npx playwright test e2e/regression.spec.ts` 或 `--grep "关键词"` 圈定；质量门禁（`verify-frontend.sh`）仍必须本地过。影响面拿不准就宁宽勿窄。注意：门禁只是静态层（lint/tsc/build），**运行时行为（水合、API 联调、交互流程）只有 E2E 能拦**（历史 P0 均如此）；且 CI 种子是 draft 组合，依赖业务数据的用例在 CI 会优雅 skip——动交互流程的改动至少要本地跑对应 spec。
- **webServer 是 production standalone**（`node .next/standalone/server.js`，:3000），**不是 `npm run dev`**——dev 按需编译竞态是历史 flaky 根因（issue #171）。
- **数据依赖**（种子见 `backend/tests/seed_base.py`）：登录 ADMIN/admin@2026（`auth.setup.ts`，storageState `e2e/.auth/admin.json`）；业务冒烟依赖 draft 组合 `E2E_PORT` + 4 平台 + 产品。
- **优雅 skip 惯例**：缺业务数据的用例 `test.skip` 而非失败（如无 pending 交易、无快照）；**新增 spec 遵循同一惯例**，但注意——若种子退化（如无组合），用例会在 CI 静默全 skip、覆盖无声蒸发，改种子时对照 `e2e/*.spec.ts` 头部「数据说明」注释。
- `auth.spec.ts` 三用例必须通过（登录是硬依赖）；platform-select-search 部分用例还需 ≥2 平台/≥2 投资人/产品。
- projects：setup / chromium（桌面）/ mobile（iPhone 13 webkit）；部分用例是端专属（另一端内 skip，属预期）。

## 其他

- `/api/:path*` 经 `next.config.js` rewrite 到 `API_BASE_URL`（默认 localhost:8000）。
- 页面清单直接看 `src/app/**/page.tsx`；移动端多为薄壳页套 `MobileLayout`。
