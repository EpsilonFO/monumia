import type { Notification } from '@/types';
import { useNotificationStore } from '@/stores/useNotificationStore';
import { generateId } from '@/lib/format-utils';

export const notificationService = {
  getByUser(userId: string): Notification[] {
    return useNotificationStore.getState().getNotificationsByUser(userId);
  },

  getUnreadCount(userId: string): number {
    return useNotificationStore.getState().getUnreadCount(userId);
  },

  markAsRead(id: string): void {
    useNotificationStore.getState().markAsRead(id);
  },

  markAllAsRead(userId: string): void {
    useNotificationStore.getState().markAllAsRead(userId);
  },

  create(notification: Omit<Notification, 'id' | 'dateCreation' | 'lue'>): Notification {
    const newNotif: Notification = {
      ...notification,
      id: `notif-${generateId()}`,
      lue: false,
      dateCreation: new Date().toISOString(),
    };
    useNotificationStore.getState().addNotification(newNotif);
    return newNotif;
  },

  delete(id: string): void {
    useNotificationStore.getState().deleteNotification(id);
  },
};
