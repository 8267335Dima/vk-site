// --- frontend/src/store/authSlice.js ---
import { disconnectWebSocket } from '../websocket';
import { jwtDecode } from 'jwt-decode';
import { apiClient } from 'api';
import { toast } from 'react-hot-toast';

export const createAuthSlice = (set, get) => ({
  jwtToken: localStorage.getItem('jwtToken') || null,
  isLoading: true,
  activeProfileId: null,
  managerId: null,

  actions: {
    login: (token) => {
      localStorage.setItem('jwtToken', token);
      const decoded = jwtDecode(token);
      set({ 
        jwtToken: token, 
        managerId: decoded.sub, 
        activeProfileId: decoded.profile_id || decoded.sub 
      });
    },
    logout: () => {
      localStorage.removeItem('jwtToken');
      disconnectWebSocket();
      get().actions.resetUserSlice(); 
      set({ jwtToken: null, isLoading: false, activeProfileId: null, managerId: null });
    },
    setActiveProfile: async (profileId) => {
      if (profileId === get().activeProfileId) return;

      try {
        const response = await apiClient.post('/api/v1/auth/switch-profile', { profile_id: profileId });
        const { access_token } = response.data;
        get().actions.login(access_token);
        window.location.reload();
      } catch (error) {
        toast.error("Не удалось переключить профиль.");
        console.error("Profile switch failed:", error);
      }
    },
    finishInitialLoad: () => {
      set({ isLoading: false });
    },
    decodeAndSetIds: () => {
      const token = get().jwtToken;
      if (token) {
        try {
          const decoded = jwtDecode(token);
          set({
            managerId: decoded.sub,
            activeProfileId: decoded.profile_id || decoded.sub
          });
        } catch (e) {
          console.error("Invalid token:", e);
          get().actions.logout();
        }
      }
    }
  }
});