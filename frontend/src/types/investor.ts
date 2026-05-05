export interface Investor {
  code: string;
  name: string;
  role: string;
  phone?: string;
  email?: string;
  last_login_at?: string;
  created_at?: string;
  updated_at?: string;
}

export interface InvestorCreate {
  code: string;
  name: string;
  role?: string;
  phone?: string;
  email?: string;
  password: string;
}

export interface InvestorUpdate {
  name?: string;
  role?: string;
  phone?: string;
  email?: string;
}
