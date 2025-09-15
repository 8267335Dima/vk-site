import { apiClient } from './index';

export const fetchProxies = () =>
  apiClient.get('/api/v1/proxies').then((res) => res.data);

export const addProxy = (proxyUrl) =>
  apiClient
    .post('/api/v1/proxies', { proxy_url: proxyUrl })
    .then((res) => res.data);

export const deleteProxy = (id) => apiClient.delete(`/api/v1/proxies/${id}`);
