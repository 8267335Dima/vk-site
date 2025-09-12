// frontend/src/store/authSlice.js
import { disconnectWebSocket } from '../websocket';

export const createAuthSlice = (set, get) => ({
  jwtToken: localStorage.getItem('jwtToken') || null,
  isLoading: true,

  actions: {
    login: (token) => {
      localStorage.setItem('jwtToken', token);
      set({ jwtToken: token });
    },
    logout: () => {
      localStorage.removeItem('jwtToken');
      disconnectWebSocket();
      get().actions.resetUserSlice(); 
      set({ jwtToken: null, isLoading: false });
    },
    finishInitialLoad: () => {
      set({ isLoading: false });
    },
  }
});