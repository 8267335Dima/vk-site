// --- frontend/src/store/authSlice.js ---
import { disconnectWebSocket } from '../websocket';
import { jwtDecode } from 'jwt-decode';
import { switchProfile } from 'api';
import { toast } from 'react-hot-toast';
import { queryClient } from 'queryClient';

export const createAuthSlice = (set, get) => ({
  jwtToken: localStorage.getItem('jwtToken') || null,
  isLoading: true,
  // ИЗМЕНЕНИЕ: ID теперь хранятся в сторе, чтобы быть доступными сразу после логина
  activeProfileId: null,
  managerId: null,

  actions: {
    login: (token) => {
      localStorage.setItem('jwtToken', token);
      set({ jwtToken: token });
      get().actions.decodeAndSetIds(); // Сразу декодируем и устанавливаем ID
    },
    logout: () => {
      localStorage.removeItem('jwtToken');
      disconnectWebSocket();
      get().actions.resetUserSlice(); 
      queryClient.clear(); // Очищаем весь кэш React Query при выходе
      set({ jwtToken: null, isLoading: false, activeProfileId: null, managerId: null });
    },
    setActiveProfile: async (profileId) => {
      if (profileId === get().activeProfileId) return;

      const toastId = toast.loading("Переключение профиля...");
      try {
        const { access_token } = await switchProfile(profileId);
        get().actions.login(access_token);
        toast.success("Профиль успешно изменен!", { id: toastId });
        await queryClient.resetQueries();
        window.location.hash = '/dashboard'; // Можно просто перенаправить
      } catch (error) {
        toast.error("Не удалось переключить профиль.", { id: toastId });
        console.error("Profile switch failed:", error);
      }
    },
    finishInitialLoad: () => {
      set({ isLoading: false });
    },
    // НОВАЯ ФУНКЦИЯ: Декодирует токен и сохраняет ID в стор
    decodeAndSetIds: () => {
      const token = get().jwtToken;
      if (token) {
        try {
          const decoded = jwtDecode(token);
          set({
            managerId: parseInt(decoded.sub, 10),
            activeProfileId: parseInt(decoded.profile_id || decoded.sub, 10)
          });
        } catch (e) {
          console.error("Invalid token:", e);
          get().actions.logout();
        }
      }
    }
  }
});