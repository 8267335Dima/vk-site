import { apiClient } from './index';

export const fetchScenarios = () =>
  apiClient.get('/api/v1/scenarios').then((res) => res.data);

export const fetchScenarioById = (id) =>
  apiClient.get(`/api/v1/scenarios/${id}`).then((res) => res.data);

export const createScenario = (data) =>
  apiClient.post('/api/v1/scenarios', data).then((res) => res.data);

export const updateScenario = (id, data) =>
  apiClient.put(`/api/v1/scenarios/${id}`, data).then((res) => res.data);

export const deleteScenario = (id) =>
  apiClient.delete(`/api/v1/scenarios/${id}`);

export const fetchAvailableConditions = () =>
  apiClient
    .get('/api/v1/scenarios/available-conditions')
    .then((res) => res.data);
