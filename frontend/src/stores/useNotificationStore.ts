import { create } from 'zustand';
import type { Notification } from '@/types';
import { mockNotifications } from '@/data/mock-notifications';

interface NotificationState {
  notifications: Notification[];

  getNotificationsByUser: (userId: string) => Notification[];
  getUnreadCount: (userId: string) => number;
  markAsRead: (id: string) => void;
  markAllAsRead: (userId: string) => void;
  addNotification: (notification: Notification) => void;
  deleteNotification: (id: string) => void;
}

export const useNotificationStore = create<NotificationState>()((set, get) => ({
  notifications: mockNotifications,

  getNotificationsByUser: (userId) =>
    get()
      .notifications.filter((n) => n.userId === userId)
      .sort(
        (a, b) =>
          new Date(b.dateCreation).getTime() -
          new Date(a.dateCreation).getTime()
      ),

  getUnreadCount: (userId) =>
    get().notifications.filter((n) => n.userId === userId && !n.lue).length,

  markAsRead: (id) =>
    set((state) => ({
      notifications: state.notifications.map((n) =>
        n.id === id ? { ...n, lue: true } : n
      ),
    })),

  markAllAsRead: (userId) =>
    set((state) => ({
      notifications: state.notifications.map((n) =>
        n.userId === userId ? { ...n, lue: true } : n
      ),
    })),

  addNotification: (notification) =>
    set((state) => ({
      notifications: [notification, ...state.notifications],
    })),

  deleteNotification: (id) =>
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id),
    })),
}));
