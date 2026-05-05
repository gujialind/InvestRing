export interface LoginRequest {
  code: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  expires_at: string;
  user: UserInfo;
}

export interface UserInfo {
  code: string;
  name: string;
  role: string;
}

export interface ChangePasswordRequest {
  target_code?: string;
  old_password?: string;
  new_password: string;
}
