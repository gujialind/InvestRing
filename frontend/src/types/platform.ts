export interface Platform {
  code: string;
  name: string;
  platform_type?: string;
  created_at?: string;
}

export interface PlatformCreate {
  code: string;
  name: string;
  platform_type?: string;
}

export interface PlatformUpdate {
  name?: string;
  platform_type?: string;
}
