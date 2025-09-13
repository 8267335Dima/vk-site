// frontend/src/store/auth.store.js
// Rationale: Этот стор теперь соответствует своему названию и хранит ТОЛЬКО состояние аутентификации.
// Вся информация о пользователе (имя, тариф и т.д.) теперь живет в кэше React Query и доступна через хук useCurrentUser.
// Это устраняет дублирование данных и делает React Query единственным источником правды для серверного состояния.
import { switchProfile } from '../api';
import { toast } from 'react-hot-toast';
import { queryClient } from '../queryClient';

export const createAuthSlice = (set, get) => ({
  token: localStorage.getItem('zenith_token') || null,
  isAuthenticated: !!localStorage.getItem('zenith_token'),
  managerId: localStorage.getItem('zenith_manager_id') || null,
  activeProfileId: localStorage.getItem('zenith_profile_id') || null,

  actions: {
    login: ({ access_token, manager_id, active_profile_id }) => {
      localStorage.setItem('zenith_token', access_token);
      localStorage.setItem('zenith_manager_id', manager_id);
      localStorage.setItem('zenith_profile_id', active_profile_id);
      set({ token: access_token, isAuthenticated: true, managerId: manager_id, activeProfileId: active_profile_id });
    },
    logout: () => {
      localStorage.removeItem('zenith_token');
      localStorage.removeItem('zenith_manager_id');
      localStorage.removeItem('zenith_profile_id');
      queryClient.clear(); // Полная очистка кэша при выходе
      set({ token: null, isAuthenticated: false, managerId: null, activeProfileId: null });
    },
    // Этот экшен вызывается из useCurrentUser при ошибке 401
    setUnauthenticated: () => {
        if (get().isAuthenticated) {
            get().actions.logout();
        }
    },
    setActiveProfile: async (profileId) => {
      if (profileId === get().activeProfileId) return;

      const toastId = toast.loading("Переключение профиля...");
      try {
        const response = await switchProfile(profileId);
        get().actions.login(response); // login теперь принимает весь объект ответа
        toast.success("Профиль успешно изменен!", { id: toastId });
        // Сброс кэша React Query, чтобы все данные были загружены для нового профиля
        await queryClient.resetQueries();
      } catch (error) {
        toast.error("Не удалось переключить профиль.", { id: toastId });
        console.error("Profile switch failed:", error);
      }
    },
  },
});