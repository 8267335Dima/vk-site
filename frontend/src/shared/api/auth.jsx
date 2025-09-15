import { apiClient } from './index';

export const loginWithVkToken = (vkToken) =>
  apiClient.post('/api/v1/auth/vk', { vk_token: vkToken });

export const switchProfile = (profileId) =>
  apiClient
    .post('/api/v1/auth/switch-profile', { profile_id: profileId })
    .then((res) => res.data);
