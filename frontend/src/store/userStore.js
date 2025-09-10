// frontend/src/store/userStore.js
import { create } from 'zustand';
import { createAuthSlice } from './authSlice';
import { createUserSlice } from './userSlice';

// Этот паттерн "собирает" глобальное состояние из отдельных модулей.
// Он уже соответствует лучшим практикам, никаких изменений не требуется.
export const useUserStore = create((set, get) => ({
  ...createAuthSlice(set, get),
  ...createUserSlice(set, get),
}));