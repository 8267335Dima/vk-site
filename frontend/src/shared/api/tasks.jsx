import { apiClient } from './index';

export const runTask = (taskKey, params) =>
  apiClient
    .post(`/api/v1/tasks/run/${taskKey}`, params)
    .then((res) => res.data);

export const fetchTaskHistory = ({ pageParam = 1 }, filters) => {
  const params = new URLSearchParams({ page: pageParam, size: 25 });
  if (filters.status) params.append('status', filters.status);
  return apiClient
    .get(`/api/v1/tasks/history?${params.toString()}`)
    .then((res) => res.data);
};

export const cancelTask = (taskHistoryId) =>
  apiClient
    .post(`/api/v1/tasks/${taskHistoryId}/cancel`)
    .then((res) => res.data);

export const retryTask = (taskHistoryId) =>
  apiClient
    .post(`/api/v1/tasks/${taskHistoryId}/retry`)
    .then((res) => res.data);

export const fetchTaskInfo = (taskKey) =>
  apiClient
    .get(`/api/v1/users/task-info?task_key=${taskKey}`)
    .then((res) => res.data);
