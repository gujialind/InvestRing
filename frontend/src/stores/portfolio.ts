import { create } from "zustand";
import { Portfolio } from "@/types/portfolio";

interface PortfolioState {
  selectedPortfolio: Portfolio | null;
  portfolios: Portfolio[];
  setSelectedPortfolio: (portfolio: Portfolio | null) => void;
  setPortfolios: (portfolios: Portfolio[]) => void;
}

export const usePortfolioStore = create<PortfolioState>((set) => ({
  selectedPortfolio: null,
  portfolios: [],
  setSelectedPortfolio: (portfolio) => set({ selectedPortfolio: portfolio }),
  setPortfolios: (portfolios) => set({ portfolios }),
}));
