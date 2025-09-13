// --- frontend/src/api.js ---
import axios from 'axios';
import { useUserStore } from 'store/userStore';

export const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL || '',
});

apiClient.interceptors.request.use((config) => {
  const token = useUserStore.getState().jwtToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      useUserStore.getState().actions.logout(); 
    }
    return Promise.reject(error);
  }
);

export const loginWithVkToken = (vkToken) => apiClient.post('/api/v1/auth/vk', { vk_token: vkToken });
export const switchProfile = (profileId) => apiClient.post('/api/v1/auth/switch-profile', { profile_id: profileId }).then(res => res.data);

export const fetchUserInfo = () => apiClient.get('/api/v1/users/me');
export const fetchUserLimits = () => apiClient.get('/api/v1/users/me/limits');
export const updateUserDelayProfile = (profile) => apiClient.put('/api/v1/users/me/delay-profile', profile);
export const fetchTaskInfo = (taskKey) => apiClient.get(`/api/v1/users/task-info?task_key=${taskKey}`);
export const getManagedProfiles = () => apiClient.get('/api/v1/users/me/managed-profiles').then(res => res.data);

export const runTask = (taskKey, params) => apiClient.post(`/api/v1/tasks/run/${taskKey}`, params);
export const fetchTaskHistory = ({ pageParam = 1 }, filters) => {
    const params = new URLSearchParams({ page: pageParam, size: 25 });
    if (filters.status) {
        params.append('status', filters.status);
    }
    return apiClient.get(`/api/v1/tasks/history?${params.toString()}`).then(res => res.data);
};
export const cancelTask = (taskHistoryId) => apiClient.post(`/api/v1/tasks/${taskHistoryId}/cancel`);
export const retryTask = (taskHistoryId) => apiClient.post(`/api/v1/tasks/${taskHistoryId}/retry`);

export const fetchActivityStats = (days = 7) => apiClient.get(`/api/v1/stats/activity?days=${days}`).then(res => res.data);
export const fetchAudienceAnalytics = () => apiClient.get('/api/v1/analytics/audience').then(res => res.data);
export const fetchProfileGrowth = (days = 30) => apiClient.get(`/api/v1/analytics/profile-growth?days=${days}`).then(res => res.data);
export const fetchProfileSummary = () => apiClient.get('/api/v1/analytics/profile-summary').then(res => res.data);
export const fetchFriendRequestConversion = () => apiClient.get('/api/v1/analytics/friend-request-conversion').then(res => res.data);
export const fetchPostActivityHeatmap = () => apiClient.get('/api/v1/analytics/post-activity-heatmap').then(res => res.data);

export const fetchAutomations = () => apiClient.get('/api/v1/automations').then(res => res.data);
export const updateAutomation = ({ automationType, isActive, settings }) => apiClient.post(`/api/v1/automations/${automationType}`, { is_active: isActive, settings: settings || {} }).then(res => res.data);

export const fetchAvailablePlans = () => apiClient.get('/api/v1/billing/plans').then(res => res.data);
export const createPayment = (planId, months) => apiClient.post('/api/v1/billing/create-payment', { plan_id: planId, months }).then(res => res.data);

// Функции для Планировщика
export const fetchPosts = () => apiClient.get('/api/v1/posts').then(res => res.data);
export const createPost = (data) => apiClient.post('/api/v1/posts', data).then(res => res.data);
export const updatePost = (id, data) => apiClient.put(`/api/v1/posts/${id}`, data).then(res => res.data);
export const deletePost = (id) => apiClient.delete(`/api/v1/posts/${id}`);
export const uploadImageForPost = (formData) => apiClient.post('/api/v1/posts/upload-image', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
}).then(res => res.data);

export const fetchScenarios = () => apiClient.get('/api/v1/scenarios').then(res => res.data);
export const fetchScenarioById = (id) => apiClient.get(`/api/v1/scenarios/${id}`).then(res => res.data);
export const createScenario = (data) => apiClient.post('/api/v1/scenarios', data).then(res => res.data);
export const updateScenario = (id, data) => apiClient.put(`/api/v1/scenarios/${id}`, data).then(res => res.data);
export const deleteScenario = (id) => apiClient.delete(`/api/v1/scenarios/${id}`);
export const fetchAvailableConditions = () => apiClient.get('/api/v1/scenarios/available-conditions').then(res => res.data);

export const fetchNotifications = () => apiClient.get('/api/v1/notifications').then(res => res.data);
export const markNotificationsAsRead = () => apiClient.post('/api/v1/notifications/read');

export const fetchProxies = () => apiClient.get('/api/v1/proxies').then(res => res.data);
export const addProxy = (proxyUrl) => apiClient.post('/api/v1/proxies', { proxy_url: proxyUrl }).then(res => res.data);
export const deleteProxy = (id) => apiClient.delete(`/api/v1/proxies/${id}`);

export const fetchFilterPresets = (actionType) => apiClient.get(`/api/v1/users/me/filter-presets?action_type=${actionType}`).then(res => res.data);
export const createFilterPreset = (data) => apiClient.post('/api/v1/users/me/filter-presets', data).then(res => res.data);
export const deleteFilterPreset = (id) => apiClient.delete(`/api/v1/users/me/filter-presets/${id}`);

// Командный функционал
export const fetchMyTeam = () => apiClient.get('/api/v1/teams/my-team').then(res => res.data);
export const inviteTeamMember = (vkId) => apiClient.post('/api/v1/teams/my-team/members', { user_vk_id: vkId });
export const removeTeamMember = (memberId) => apiClient.delete(`/api/v1/teams/my-team/members/${memberId}`);
export const updateMemberAccess = (memberId, accesses) => apiClient.put(`/api/v1/teams/my-team/members/${memberId}/access`, accesses);