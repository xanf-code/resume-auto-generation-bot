export interface Notification {
  id: string;
  jobId: string;
  label: string;
  score?: number;
  at: string;
}

export interface NotificationsState {
  notifications: Notification[];
}

export interface NotificationsActions {
  addNotification: (n: Omit<Notification, 'id' | 'at'>) => void;
  clearNotifications: () => void;
}
