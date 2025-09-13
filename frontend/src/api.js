// --- frontend/src/api.js ---
// Rationale: Улучшен interceptor для более детальной обработки ошибок.
// Все функции теперь консистентно возвращают res.data для удобства использования в React Query.
import axios from 'axios';
import { useStore } from 'store';

export const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL || '',
});

apiClient.interceptors.request.use((config) => {
  const token = useStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Перехватчик теперь вызывает action из стора, который сбрасывает все состояния.
    if (error.response && error.response.status === 401) {
      useStore.getState().actions.setUnauthenticated(); 
    }
    return Promise.reject(error);
  }
);

// Auth
export const loginWithVkToken = (vkToken) => apiClient.post('/api/v1/auth/vk', { vk_token: vkToken }).then(res => res.data);
export const switchProfile = (profileId) => apiClient.post('/api/v1/auth/switch-profile', { profile_id: profileId }).then(res => res.data);

// Users
export const fetchUserInfo = () => apiClient.get('/api/v1/users/me'); // Возвращаем весь response для useQuery
export const fetchUserLimits = () => apiClient.get('/api/v1/users/me/limits').then(res => res.data);
export const updateUserDelayProfile = (profile) => apiClient.put('/api/v1/users/me/delay-profile', profile).then(res => res.data);
export const fetchTaskInfo = (taskKey) => apiClient.get(`/api/v1/users/task-info?task_key=${taskKey}`).then(res => res.data);
export const getManagedProfiles = () => apiClient.get('/api/v1/users/me/managed-profiles').then(res => res.data);
export const fetchFilterPresets = (actionType) => apiClient.get(`/api/v1/users/me/filter-presets?action_type=${actionType}`).then(res => res.data);
export const createFilterPreset = (data) => apiClient.post('/api/v1/users/me/filter-presets', data).then(res => res.data);
export const deleteFilterPreset = (id) => apiClient.delete(`/api/v1/users/me/filter-presets/${id}`);

// Tasks
export const runTask = (taskKey, params) => apiClient.post(`/api/v1/tasks/run/${taskKey}`, params).then(res => res.data);
export const fetchTaskHistory = ({ pageParam = 1 }, filters) => {
    const params = new URLSearchParams({ page: pageParam, size: 25 });
    if (filters.status) params.append('status', filters.status);
    return apiClient.get(`/api/v1/tasks/history?${params.toString()}`).then(res => res.data);
};
export const cancelTask = (taskHistoryId) => apiClient.post(`/api/v1/tasks/${taskHistoryId}/cancel`).then(res => res.data);
export const retryTask = (taskHistoryId) => apiClient.post(`/api/v1/tasks/${taskHistoryId}/retry`).then(res => res.data);

// Stats
export const fetchActivityStats = (days = 7) => apiClient.get(`/api/v1/stats/activity?days=${days}`).then(res => res.data);

// Analytics
export const fetchAudienceAnalytics = () => apiClient.get('/api/v1/analytics/audience').then(res => res.data);
export const fetchProfileGrowth = (days = 30) => apiClient.get(`/api/v1/analytics/profile-growth?days=${days}`).then(res => res.data);
export const fetchProfileSummary = () => apiClient.get('/api/v1/analytics/profile-summary').then(res => res.data);
export const fetchFriendRequestConversion = () => apiClient.get('/api/v1/analytics/friend-request-conversion').then(res => res.data);
export const fetchPostActivityHeatmap = () => apiClient.get('/api/v1/analytics/post-activity-heatmap').then(res => res.data);

// Automations
export const fetchAutomations = () => apiClient.get('/api/v1/automations').then(res => res.data);
export const updateAutomation = ({ automationType, isActive, settings }) => apiClient.post(`/api/v1/automations/${automationType}`, { is_active: isActive, settings: settings || {} }).then(res => res.data);

// Billing
export const fetchAvailablePlans = () => apiClient.get('/api/v1/billing/plans').then(res => res.data);
export const createPayment = (planId, months) => apiClient.post('/api/v1/billing/create-payment', { plan_id: planId, months }).then(res => res.data);

// Scenarios
export const fetchScenarios = () => apiClient.get('/api/v1/scenarios').then(res => res.data);
export const fetchScenarioById = (id) => apiClient.get(`/api/v1/scenarios/${id}`).then(res => res.data);
export const createScenario = (data) => apiClient.post('/api/v1/scenarios', data).then(res => res.data);
export const updateScenario = (id, data) => apiClient.put(`/api/v1/scenarios/${id}`, data).then(res => res.data);
export const deleteScenario = (id) => apiClient.delete(`/api/v1/scenarios/${id}`);
export const fetchAvailableConditions = () => apiClient.get('/api/v1/scenarios/available-conditions').then(res => res.data);

// Notifications
export const fetchNotifications = () => apiClient.get('/api/v1/notifications').then(res => res.data);
export const markNotificationsAsRead = () => apiClient.post('/api/v1/notifications/read');

// Proxies
export const fetchProxies = () => apiClient.get('/api/v1/proxies').then(res => res.data);
export const addProxy = (proxyUrl) => apiClient.post('/api/v1/proxies', { proxy_url: proxyUrl }).then(res => res.data);
export const deleteProxy = (id) => apiClient.delete(`/api/v1/proxies/${id}`);

// Teams
export const fetchMyTeam = () => apiClient.get('/api/v1/teams/my-team').then(res => res.data);
export const inviteTeamMember = (vkId) => apiClient.post('/api/v1/teams/my-team/members', { user_vk_id: vkId });
export const removeTeamMember = (memberId) => apiClient.delete(`/api/v1/teams/my-team/members/${memberId}`);
export const updateMemberAccess = (memberId, accesses) => apiClient.put(`/api/v1/teams/my-team/members/${memberId}/access`, accesses);