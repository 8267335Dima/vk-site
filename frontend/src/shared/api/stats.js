import { apiClient } from './index';

export const fetchActivityStats = (days = 7) =>
  apiClient.get(`/api/v1/stats/activity?days=${days}`).then((res) => res.data);
