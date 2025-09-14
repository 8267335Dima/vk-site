import { apiClient } from './index';

export const fetchNotifications = () =>
  apiClient.get('/api/v1/notifications').then((res) => res.data);

export const markNotificationsAsRead = () =>
  apiClient.post('/api/v1/notifications/read');
