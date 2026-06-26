export interface NotificationItem {
  id: number;
  title: string;
  content: string;
  status: string;
  is_read?: boolean;
  created_at: string;
}
