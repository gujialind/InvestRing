import { request } from "./client";
import { Investor, InvestorCreate, InvestorUpdate } from "@/types/investor";
import { PaginatedResponse } from "@/types/common";

export const investorApi = {
  list: (params?: { page?: number; page_size?: number }) =>
    request<PaginatedResponse<Investor>>({ method: "GET", url: "/investors", params }),

  get: (code: string) =>
    request<Investor>({ method: "GET", url: `/investors/${code}` }),

  create: (data: InvestorCreate) =>
    request<Investor>({ method: "POST", url: "/investors", data }),

  update: (code: string, data: InvestorUpdate) =>
    request<Investor>({ method: "PUT", url: `/investors/${code}`, data }),

  remove: (code: string) =>
    request<{ message: string }>({ method: "DELETE", url: `/investors/${code}` }),
};
