// 字段与后端 schemas/notification.py::NotificationResponse 对齐
export interface NotificationItem {
  id: number;
  type: string;
  level: string; // info / warning / error
  title: string;
  content?: string;
  recipient?: string;
  channel: string;
  status: string; // pending / sent / read
  sent_at?: string;
  read_at?: string;
  created_at?: string;
}
