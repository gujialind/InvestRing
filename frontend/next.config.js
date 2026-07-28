/** @type {import('next').NextConfig} */

// 后端 API 地址：Docker 环境下使用容器名，本地开发使用 localhost
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

const nextConfig = {
  reactStrictMode: true,
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
