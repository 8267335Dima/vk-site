import { apiClient } from './index';

export const fetchMyTeam = () =>
  apiClient.get('/api/v1/teams/my-team').then((res) => res.data);

export const inviteTeamMember = (vkId) =>
  apiClient.post('/api/v1/teams/my-team/members', { user_vk_id: vkId });

export const removeTeamMember = (memberId) =>
  apiClient.delete(`/api/v1/teams/my-team/members/${memberId}`);

export const updateMemberAccess = (memberId, accesses) =>
  apiClient.put(`/api/v1/teams/my-team/members/${memberId}/access`, accesses);
