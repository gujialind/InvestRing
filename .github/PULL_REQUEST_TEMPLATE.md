## 改动内容

<!-- 本次改动做了什么，涉及哪些模块。 -->

## 关联 issue

<!-- 格式：fixes #N（合并后自动关闭对应 issue）。 -->

- fixes #

## 测试验证

<!-- 勾选已执行的验证项，并附关键结果。合入 main 前 CI 必须全绿。 -->

- [ ] 本地 pytest（backend）
- [ ] MySQL 迁移链检查（CI backend-test-mysql）
- [ ] ir-cli 契约检查（CI cli-contract-check）
- [ ] 前端 lint / build（CI frontend-check）
- [ ] 上线冒烟（health check + `ir portfolio list` + 关键数据抽查）

## 部署影响

<!-- 有无 DB 迁移 / 新依赖 / 配置变更；如有，写明回滚要点。 -->
