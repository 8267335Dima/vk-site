import { apiClient } from './index';

export const fetchUserInfo = () => apiClient.get('/api/v1/users/me');
export const fetchUserLimits = () =>
  apiClient.get('/api/v1/users/me/limits').then((res) => res.data);
export const updateUserDelayProfile = (profile) =>
  apiClient
    .put('/api/v1/users/me/delay-profile', profile)
    .then((res) => res.data);
export const getManagedProfiles = () =>
  apiClient.get('/api/v1/users/me/managed-profiles').then((res) => res.data);
export const fetchFilterPresets = (actionType) =>
  apiClient
    .get(`/api/v1/users/me/filter-presets?action_type=${actionType}`)
    .then((res) => res.data);
export const createFilterPreset = (data) =>
  apiClient
    .post('/api/v1/users/me/filter-presets', data)
    .then((res) => res.data);
export const deleteFilterPreset = (id) =>
  apiClient.delete(`/api/v1/users/me/filter-presets/${id}`);
