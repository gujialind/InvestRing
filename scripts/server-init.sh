#!/bin/bash
# ============================================================================
# InvestRing 服务器初始化脚本
# ============================================================================
# 目标环境：阿里云轻量应用服务器 2核2GB (Ubuntu 22.04)
# 功能：配置 swap、安装 Docker、创建部署目录、设置防火墙
# 使用方式：ssh root@your-server-ip 后执行此脚本
# ============================================================================

set -e

echo "============================================"
echo "  InvestRing 服务器初始化"
echo "  目标：2核2GB 轻量服务器 + RDS MySQL"
echo "============================================"

# ------------------------------------------------------------------
# 1. 系统更新
# ------------------------------------------------------------------
echo ""
echo "[1/6] 更新系统包..."
apt-get update -qq
apt-get upgrade -y -qq

# ------------------------------------------------------------------
# 2. 配置 Swap（2GB 内存必须，防止 OOM）
# ------------------------------------------------------------------
echo ""
echo "[2/6] 配置 Swap..."

if [ -f /swapfile ]; then
    echo "Swap 已存在，跳过"
else
    # 创建 2GB swap 文件
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile

    # 写入 fstab 持久化
    if ! grep -q '/swapfile' /etc/fstab; then
        echo '/swapfile none swap sw 0 0' >> /etc/fstab
    fi

    # 优化 swap 使用策略（减少不必要的换页）
    sysctl vm.swappiness=10
    if ! grep -q 'vm.swappiness' /etc/sysctl.conf; then
        echo 'vm.swappiness=10' >> /etc/sysctl.conf
    fi

    # 优化内存回收策略
    sysctl vm.vfs_cache_pressure=50
    if ! grep -q 'vm.vfs_cache_pressure' /etc/sysctl.conf; then
        echo 'vm.vfs_cache_pressure=50' >> /etc/sysctl.conf
    fi

    echo "✅ Swap 已启用 (2GB, swappiness=10)"
fi

# 验证 swap
free -h | grep -i swap

# ------------------------------------------------------------------
# 3. 安装 Docker 和 Docker Compose
# ------------------------------------------------------------------
echo ""
echo "[3/6] 安装 Docker..."

if command -v docker &> /dev/null; then
    echo "Docker 已安装: $(docker --version)"
else
    # 使用阿里云镜像加速安装（国内服务器速度快）
    curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg | apt-key add -
    add-apt-repository "deb [arch=amd64] https://mirrors.aliyun.com/docker-ce/linux/ubuntu $(lsb_release -cs) stable"
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin

    # 启动并设置开机自启
    systemctl enable docker
    systemctl start docker

    echo "✅ Docker 安装完成: $(docker --version)"
fi

# 配置 Docker 镜像加速（拉取 GHCR/Docker Hub 镜像更快）
if [ ! -f /etc/docker/daemon.json ]; then
    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json << 'DAEMON_EOF'
{
    "registry-mirrors": [
        "https://mirror.ccs.tencentyun.com",
        "https://docker.mirrors.ustc.edu.cn"
    ],
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "3"
    },
    "storage-driver": "overlay2"
}
DAEMON_EOF
    systemctl daemon-reload
    systemctl restart docker
    echo "✅ Docker 镜像加速已配置"
fi

# ------------------------------------------------------------------
# 4. 创建部署目录
# ------------------------------------------------------------------
echo ""
echo "[4/6] 创建部署目录..."

DEPLOY_PATH="/opt/investring"
mkdir -p $DEPLOY_PATH/nginx
echo "✅ 部署目录已创建: $DEPLOY_PATH"

# ------------------------------------------------------------------
# 5. 配置防火墙（阿里云轻量服务器需要在控制台也配置）
# ------------------------------------------------------------------
echo ""
echo "[5/6] 配置系统防火墙..."

# 如果安装了 ufw
if command -v ufw &> /dev/null; then
    ufw allow 22/tcp    # SSH
    ufw allow 80/tcp    # HTTP
    ufw allow 443/tcp   # HTTPS
    ufw --force enable
    echo "✅ UFW 防火墙已配置"
else
    echo "⚠️ 未安装 ufw，请在阿里云控制台配置安全组/防火墙规则"
fi

echo ""
echo "⚠️  重要：请在阿里云轻量服务器控制台 → 防火墙 中放行以下端口："
echo "    - 22 (SSH)"
echo "    - 80 (HTTP)"
echo "    - 443 (HTTPS)"

# ------------------------------------------------------------------
# 6. 创建部署用户（安全：不使用 root 运行业务）
# ------------------------------------------------------------------
echo ""
echo "[6/6] 创建部署用户..."

DEPLOY_USER="deploy"
if id "$DEPLOY_USER" &> /dev/null; then
    echo "用户 $DEPLOY_USER 已存在"
else
    useradd -m -s /bin/bash $DEPLOY_USER
    # 将 deploy 用户加入 docker 组（免 sudo 运行 docker）
    usermod -aG docker $DEPLOY_USER
    echo "✅ 部署用户已创建: $DEPLOY_USER"
fi

# 设置部署目录权限
chown -R $DEPLOY_USER:$DEPLOY_USER $DEPLOY_PATH

# ------------------------------------------------------------------
# 完成
# ------------------------------------------------------------------
echo ""
echo "============================================"
echo "  ✅ 服务器初始化完成！"
echo "============================================"
echo ""
echo "系统信息："
echo "  OS:     $(lsb_release -ds)"
echo "  Kernel: $(uname -r)"
echo "  CPU:    $(nproc) cores"
echo "  Memory: $(free -h | awk '/Mem:/ {print $2}')"
echo "  Swap:   $(free -h | awk '/Swap:/ {print $2}')"
echo "  Docker: $(docker --version)"
echo ""
echo "下一步操作："
echo "  1. 在阿里云控制台防火墙中放行 80/443 端口"
echo "  2. 在 RDS 白名单中添加本服务器内网 IP"
echo "  3. 配置 GitHub Secrets（见部署指南）"
echo "  4. 上传 nginx.conf 和 docker-compose.yml 到 $DEPLOY_PATH"
echo ""
echo "部署目录: $DEPLOY_PATH"
echo "部署用户: $DEPLOY_USER"
