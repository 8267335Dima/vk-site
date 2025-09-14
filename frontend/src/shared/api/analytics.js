import { apiClient } from './index';

export const fetchAudienceAnalytics = () =>
  apiClient.get('/api/v1/analytics/audience').then((res) => res.data);

export const fetchProfileGrowth = (days = 30) =>
  apiClient
    .get(`/api/v1/analytics/profile-growth?days=${days}`)
    .then((res) => res.data);

export const fetchProfileSummary = () =>
  apiClient.get('/api/v1/analytics/profile-summary').then((res) => res.data);

export const fetchFriendRequestConversion = () =>
  apiClient
    .get('/api/v1/analytics/friend-request-conversion')
    .then((res) => res.data);

export const fetchPostActivityHeatmap = () =>
  apiClient
    .get('/api/v1/analytics/post-activity-heatmap')
    .then((res) => res.data);
