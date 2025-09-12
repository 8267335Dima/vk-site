// frontend/src/api.js
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

// --- Auth ---
export const loginWithVkToken = (vkToken) => apiClient.post('/api/v1/auth/vk', { vk_token: vkToken });

// --- User ---
export const fetchUserInfo = () => apiClient.get('/api/v1/users/me');
export const fetchUserLimits = () => apiClient.get('/api/v1/users/me/limits');
export const updateUserDelayProfile = (profile) => apiClient.put('/api/v1/users/me/delay-profile', profile);
export const fetchTaskInfo = (taskKey) => apiClient.get(`/api/v1/users/task-info?task_key=${taskKey}`);

// --- Tasks & History ---
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

// --- Stats & Analytics ---
export const fetchActivityStats = (days = 7) => apiClient.get(`/api/v1/stats/activity?days=${days}`).then(res => res.data);
export const fetchAudienceAnalytics = () => apiClient.get('/api/v1/analytics/audience').then(res => res.data);
export const fetchProfileGrowth = (days = 30) => apiClient.get(`/api/v1/analytics/profile-growth?days=${days}`).then(res => res.data);
export const fetchProfileSummary = () => apiClient.get('/api/v1/analytics/profile-summary').then(res => res.data);

// --- Automations ---
export const fetchAutomations = () => apiClient.get('/api/v1/automations').then(res => res.data);
export const updateAutomation = ({ automationType, isActive, settings }) => apiClient.post(`/api/v1/automations/${automationType}`, { is_active: isActive, settings: settings || {} }).then(res => res.data);

// --- Billing ---
export const fetchAvailablePlans = () => apiClient.get('/api/v1/billing/plans').then(res => res.data);
export const createPayment = (planId, months) => apiClient.post('/api/v1/billing/create-payment', { plan_id: planId, months }).then(res => res.data);

// --- Scenarios ---
export const fetchScenarios = () => apiClient.get('/api/v1/scenarios').then(res => res.data);
export const createScenario = (data) => apiClient.post('/api/v1/scenarios', data).then(res => res.data);
export const updateScenario = ({ id, ...data }) => apiClient.put(`/api/v1/scenarios/${id}`, data).then(res => res.data);
export const deleteScenario = (id) => apiClient.delete(`/api/v1/scenarios/${id}`);

// --- Notifications ---
export const fetchNotifications = () => apiClient.get('/api/v1/notifications').then(res => res.data);
export const markNotificationsAsRead = () => apiClient.post('/api/v1/notifications/read');

// --- Proxies ---
export const fetchProxies = () => apiClient.get('/api/v1/proxies').then(res => res.data);
export const addProxy = (proxyUrl) => apiClient.post('/api/v1/proxies', { proxy_url: proxyUrl }).then(res => res.data);
export const deleteProxy = (id) => apiClient.delete(`/api/v1/proxies/${id}`);