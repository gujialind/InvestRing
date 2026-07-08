"use client";

import { useQuery } from "@tanstack/react-query";
import { platformApi } from "@/lib/api";

const PLATFORM_QUERY_KEY = "platforms";

// 平台列表 Hook
export function usePlatformList(params?: { page?: number; page_size?: number }) {
  return useQuery({
    queryKey: [PLATFORM_QUERY_KEY, "list", params],
    queryFn: () => platformApi.list(params),
    staleTime: 60 * 1000,
  });
}

// 单个平台详情 Hook
export function usePlatform(code: string) {
  return useQuery({
    queryKey: [PLATFORM_QUERY_KEY, code],
    queryFn: () => platformApi.get(code),
    enabled: !!code,
    staleTime: 60 * 1000,
  });
}
