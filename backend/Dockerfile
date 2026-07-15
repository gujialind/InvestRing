# ============================================================================
# InvestRing 后端 Dockerfile
# ============================================================================
# 基于 Python 3.11-slim，多阶段构建优化镜像大小
# 上下文：项目根目录（docker build -f backend/Dockerfile .）
# ============================================================================

# ------------------------------------------------------------------
# 阶段 1：依赖安装层（利用 Docker 缓存加速构建）
# ------------------------------------------------------------------
FROM python:3.11-slim AS deps

WORKDIR /app

# 使用阿里云 Debian 镜像（国内加速）
RUN sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖（pymysql 编译需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件，利用 Docker 层缓存
COPY backend/requirements.txt .

# 安装 Python 依赖（使用阿里云 PyPI 镜像，国内加速）
RUN pip install --no-cache-dir --prefix=/install --only-binary :all: \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    -r requirements.txt

# ------------------------------------------------------------------
# 阶段 2：生产运行层（最小化镜像体积）
# ------------------------------------------------------------------
FROM python:3.11-slim AS runtime

WORKDIR /app

# 使用阿里云 Debian 镜像（国内加速）
RUN sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources

# 安装运行时必要的系统库（不含 gcc 等编译工具）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    # 创建非 root 用户运行应用（安全最佳实践）
    && groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# 从 deps 阶段复制已安装的 Python 包
COPY --from=deps /install /usr/local

# 复制后端应用代码
COPY backend/ .

# 设置 Python 环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1

# 创建日志目录
RUN mkdir -p /app/logs && chown -R appuser:appuser /app

# 切换到非 root 用户
USER appuser

# 暴露 FastAPI 端口
EXPOSE 8000

# 健康检查：每 30 秒检测一次后端服务是否存活
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令：使用 uvicorn 运行 FastAPI 应用
# --host 0.0.0.0 允许外部访问
# --workers 2 适配 2 核轻量服务器（每个 worker 约 80-120MB）
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
