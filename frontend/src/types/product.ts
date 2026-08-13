export interface Product {
  code: string;
  market?: string;
  name: string;
  product_type: string;
  // 五维度标签（issue #128）：股票必填 region/style/size；债券必填 region+segment；
  // 商品/现金 region/style/size 为 NULL；IN_TRANSIT 虚拟产品全 NULL
  asset_class_code?: string | null;
  region_code?: string | null;
  style_code?: string | null;
  size_code?: string | null;
  segment_code?: string | null;
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
  region_code?: string;
  style_code?: string;
  size_code?: string;
  segment_code?: string;
  confirm_days?: number;
  is_qdii?: boolean;
  /** 数据源（后端默认 tushare） */
  data_source?: string;
  /** issue #90：创建后立即回填历史净值（同步失败不阻断创建） */
  sync_history?: boolean;
}

export interface ProductUpdate {
  name?: string;
  // 维度字段允许显式 null（清空）：后端 exclude_unset 语义下 null 会进入合并校验
  asset_class_code?: string | null;
  region_code?: string | null;
  style_code?: string | null;
  size_code?: string | null;
  segment_code?: string | null;
  confirm_days?: number;
  is_qdii?: boolean;
}
