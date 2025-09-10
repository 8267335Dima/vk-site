// frontend/src/api.js
import axios from 'axios';
import { useUserStore } from 'store/userStore';

// --- ИЗМЕНЕНИЕ: Экспортируем apiClient для прямого использования в виджетах ---
export const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL || '',
});
// ... остальной код без изменений ...
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
      useUserStore.getState().logout();
    }
    return Promise.reject(error);
  }
);
// --- Auth ---
export const loginWithVkToken = (vkToken) => {
  return apiClient.post('/api/v1/auth/vk', { vk_token: vkToken });
};

// --- User ---
export const fetchUserInfo = () => apiClient.get('/api/v1/users/me');
export const fetchTaskInfo = (taskKey) => apiClient.get(`/api/v1/users/task-info?task_key=${taskKey}`);


// --- Tasks (Actions) ---
const runTask = (endpoint, params) => apiClient.post(`/api/v1/tasks/run${endpoint}`, params);
export const runAcceptFriends = (params) => runTask('/accept-friends', params);
export const runLikeFeed = (params) => runTask('/like-feed', params);
export const runAddRecommended = (params) => runTask('/add-recommended-friends', params);
export const runViewStories = (params) => runTask('/view-stories', params);
export const runLikeFriendsFeed = (params) => runTask('/like-friends-feed', params);
export const runRemoveFriends = (params) => runTask('/remove-friends', params);


// --- Task History ---
export const fetchTaskHistory = async ({ pageParam = 1 }, filter = null) => {
    const params = new URLSearchParams({ page: pageParam, size: 25 });
    if (filter) params.append('status', filter);
    return (await apiClient.get(`/api/v1/tasks/history?${params.toString()}`)).data;
};

// --- Stats & Analytics ---
export const fetchActivityStats = async (days = 7) => (await apiClient.get(`/api/v1/stats/activity?days=${days}`)).data;
export const fetchFriendsAnalytics = async () => (await apiClient.get('/api/v1/stats/friends-analytics')).data;
export const fetchAudienceAnalytics = async () => (await apiClient.get('/api/v1/analytics/audience')).data;
export const fetchFriendsDynamic = async (days = 30) => (await apiClient.get(`/api/v1/analytics/friends-dynamic?days=${days}`)).data;
export const fetchActionSummary = async (days = 30) => (await apiClient.get(`/api/v1/analytics/actions-summary?days=${days}`)).data;

// --- Logs ---
export const fetchActionLogs = async ({ pageParam = 1 }, filter = null) => {
    const params = new URLSearchParams({ page: pageParam, size: 25 });
    if (filter) params.append('action_type', filter);
    return (await apiClient.get(`/api/v1/logs?${params.toString()}`)).data;
};

// --- Automations ---
export const fetchAutomations = async () => (await apiClient.get('/api/v1/automations')).data;
export const updateAutomation = async ({ automationType, isActive, settings }) => (await apiClient.post(`/api/v1/automations/${automationType}`, { is_active: isActive, settings: settings || {} })).data;

// --- Billing ---
export const fetchAvailablePlans = async () => (await apiClient.get('/api/v1/billing/plans')).data;
export const createPayment = async (planName) => (await apiClient.post('/api/v1/billing/create-payment', { plan_name: planName })).data;

// --- Scenarios ---
export const fetchScenarios = async () => (await apiClient.get('/api/v1/scenarios')).data;
export const createScenario = async (scenarioData) => (await apiClient.post('/api/v1/scenarios', scenarioData)).data;
export const updateScenario = async ({ id, ...scenarioData }) => (await apiClient.put(`/api/v1/scenarios/${id}`, scenarioData)).data;
export const deleteScenario = async (id) => { await apiClient.delete(`/api/v1/scenarios/${id}`); return id; };

// --- Notifications ---
export const fetchNotifications = async () => (await apiClient.get('/api/v1/notifications')).data;
export const markNotificationsAsRead = async () => (await apiClient.post('/api/v1/notifications/read')).data;