# ============================================================================
# InvestRing 前端 Dockerfile
# ============================================================================
# 基于 Node.js 多阶段构建，最终使用 Nginx 或直接运行 Next.js
# 上下文：项目根目录（docker build -f frontend/Dockerfile .）
# ============================================================================

# ------------------------------------------------------------------
# 阶段 1：安装依赖
# ------------------------------------------------------------------
FROM node:20-alpine AS deps

WORKDIR /app

# 先复制包文件，利用 Docker 层缓存
COPY frontend/package.json frontend/package-lock.json ./

# 使用 ci 确保依赖与锁文件完全一致（CI/CD 推荐）
RUN npm ci --only=production=false

# ------------------------------------------------------------------
# 阶段 2：构建 Next.js 应用
# ------------------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

# 复制依赖和源码
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ .

# 构建时注入环境变量
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

# Next.js 构建（生成 .next/ 目录）
RUN npm run build

# ------------------------------------------------------------------
# 阶段 3：生产运行层（最小化镜像）
# ------------------------------------------------------------------
FROM node:20-alpine AS runtime

WORKDIR /app

# 安全：创建非 root 用户
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# 复制构建产物
COPY --from=builder /app/public ./public

# 启用 Next.js Standalone 输出模式需要下面的复制方式
# 如果 next.config.js 中配置了 output: 'standalone'，则使用 standalone 目录
# 否则复制完整构建产物

# 标准模式：复制 .next 和 node_modules
COPY --from=builder --chown=nextjs:nodejs /app/.next ./.next
COPY --from=builder --chown=nextjs:nodejs /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/next.config.js ./next.config.js
COPY --from=builder /app/tailwind.config.ts ./tailwind.config.ts
COPY --from=builder /app/postcss.config.js ./postcss.config.js

# 环境变量
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME="0.0.0.0"

# 切换到非 root 用户
USER nextjs

# 暴露 Next.js 端口
EXPOSE 3000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

# 启动 Next.js 生产服务器
CMD ["node_modules/.bin/next", "start", "-H", "0.0.0.0", "-p", "3000"]
