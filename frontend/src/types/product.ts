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
  /** 数据源（后端默认 tushare） */
  data_source?: string;
  /** issue #90：创建后立即回填历史净值（同步失败不阻断创建） */
  sync_history?: boolean;
}

export interface ProductUpdate {
  name?: string;
  asset_class_code?: string;
  confirm_days?: number;
  is_qdii?: boolean;
}
