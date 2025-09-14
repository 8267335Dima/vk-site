import { apiClient } from './index';

export const fetchAutomations = () =>
  apiClient.get('/api/v1/automations').then((res) => res.data);

export const updateAutomation = ({ automationType, isActive, settings }) =>
  apiClient
    .post(`/api/v1/automations/${automationType}`, {
      is_active: isActive,
      settings: settings || {},
    })
    .then((res) => res.data);
