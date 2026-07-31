/**
 * 根路径占位：实际重定向由 src/middleware.ts 在服务端完成
 * （移动端 → /m/dashboard，PC → /dashboard），此处无需客户端跳转，
 * 避免"服务端重定向 + 客户端 router.push"双重跳转导致首屏白屏一帧。
 */
export default function Home() {
  return null;
}
