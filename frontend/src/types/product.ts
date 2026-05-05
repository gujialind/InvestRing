export interface Product {
  code: string;
  market?: string;
  name: string;
  product_type: string;
  asset_class_code?: string;
  confirm_days: number;
  is_qdii: boolean;
  data_source?: string;
  data_source_status: string;
  last_sync_at?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ProductCreate {
  code: string;
  market?: string;
  name: string;
  product_type: string;
  asset_class_code?: string;
  confirm_days?: number;
  is_qdii?: boolean;
}

export interface ProductUpdate {
  name?: string;
  asset_class_code?: string;
  confirm_days?: number;
  is_qdii?: boolean;
}
