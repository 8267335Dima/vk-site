import { toast } from 'react-hot-toast';
import { switchProfile } from '@/shared/api/api';
import { queryClient } from '@/shared/api/queryClient';

export const createAuthSlice = (set, get) => ({
  token: localStorage.getItem('zenith_token') || null,
  isAuthenticated: !!localStorage.getItem('zenith_token'),
  managerId: localStorage.getItem('zenith_manager_id') || null,
  activeProfileId: localStorage.getItem('zenith_profile_id') || null,
  userInfo: null,

  actions: {
    setUserInfo: (info) => set({ userInfo: info }),
    login: ({ access_token, manager_id, active_profile_id }) => {
      localStorage.setItem('zenith_token', access_token);
      localStorage.setItem('zenith_manager_id', manager_id);
      localStorage.setItem('zenith_profile_id', active_profile_id);
      set({
        token: access_token,
        isAuthenticated: true,
        managerId: manager_id,
        activeProfileId: active_profile_id,
      });
    },
    logout: () => {
      localStorage.removeItem('zenith_token');
      localStorage.removeItem('zenith_manager_id');
      localStorage.removeItem('zenith_profile_id');
      queryClient.clear();
      set({
        token: null,
        isAuthenticated: false,
        managerId: null,
        activeProfileId: null,
        userInfo: null,
      });
    },
    setUnauthenticated: () => {
      if (get().isAuthenticated) {
        get().actions.logout();
      }
    },
    setActiveProfile: async (profileId) => {
      const currentId = get().activeProfileId;
      if (Number(profileId) === Number(currentId)) return;

      const toastId = toast.loading('Переключение профиля...');
      try {
        const response = await switchProfile(profileId);
        get().actions.login(response);
        toast.success('Профиль успешно изменен!', { id: toastId });
        await queryClient.resetQueries();
      } catch (error) {
        toast.error('Не удалось переключить профиль.', { id: toastId });
        console.error('Profile switch failed:', error);
      }
    },
  },
});
