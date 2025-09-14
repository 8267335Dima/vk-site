import { apiClient } from './index';

export const fetchAvailablePlans = () =>
  apiClient.get('/api/v1/billing/plans').then((res) => res.data);

export const createPayment = (planId, months) =>
  apiClient
    .post('/api/v1/billing/create-payment', { plan_id: planId, months })
    .then((res) => res.data);
