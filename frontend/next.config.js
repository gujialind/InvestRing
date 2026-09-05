/** @type {import('next').NextConfig} */

// 后端 API 地址：Docker 环境下使用容器名，本地开发使用 localhost
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

// 项目版本（#375）：package.json version 由发布脚本从仓库根 VERSION 同步，构建期注入
const { version } = require('./package.json');

const nextConfig = {
  reactStrictMode: true,
  // 设置页「系统信息」版本号来源（双端共享 SettingsContent）
  env: {
    NEXT_PUBLIC_APP_VERSION: version,
  },
  // Standalone 输出：仅打包运行所需的最小依赖，供 Docker 镜像使用（大幅减小体积）
  output: 'standalone',
  // 多 lockfile 场景下显式指定 workspace root，消除 Next 的根目录推断告警
  outputFileTracingRoot: __dirname,
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${API_BASE_URL}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
