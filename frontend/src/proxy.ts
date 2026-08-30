import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  const userAgent = request.headers.get("user-agent") || "";
  const isMobile = /Mobile|Android|iPhone|iPad|iPod/i.test(userAgent);
  const pathname = request.nextUrl.pathname;
  const token = request.cookies.get("token")?.value;

  if (pathname.startsWith("/_next") || pathname.startsWith("/api")) {
    return NextResponse.next();
  }

  if (pathname === "/") {
    const target = isMobile ? "/m/dashboard" : "/dashboard";
    return NextResponse.redirect(new URL(target, request.url));
  }

  if (isMobile && !pathname.startsWith("/m") && pathname !== "/login") {
    const mobilePath = "/m" + pathname;
    return NextResponse.redirect(new URL(mobilePath, request.url));
  }

  if (!isMobile && pathname.startsWith("/m")) {
    const desktopPath = pathname.slice(2) || "/";
    return NextResponse.redirect(new URL(desktopPath, request.url));
  }

  const isLoginPage = pathname === "/m/login" || pathname === "/login";
  if (!token && !isLoginPage) {
    const loginPath = isMobile ? "/m/login" : "/login";
    return NextResponse.redirect(new URL(loginPath, request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};