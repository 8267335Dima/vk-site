// РЕФАКТОРИНГ: Этот файл теперь является точкой входа,
// которая собирает и экспортирует все API-методы и клиент.
import axios from 'axios';
import { useStore } from '@/app/store';

// Базовый клиент остается здесь, он общий для всех.
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
});

apiClient.interceptors.request.use((config) => {
  const token = useStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Экспортируем все функции из разделенных модулей
export * from './auth';
export * from './users';
export * from './tasks';
export * from './analytics';
export * from './stats';
export * from './automations';
export * from './billing';
export * from './scenarios';
export * from './notifications';
export * from './proxies';
export * from './teams';
export * from './posts';
