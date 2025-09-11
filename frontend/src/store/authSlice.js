// frontend/src/store/authSlice.js
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
      get().actions.resetUserSlice(); 
      set({ jwtToken: null, isLoading: false });
    },
    finishInitialLoad: () => {
      set({ isLoading: false });
    },
  }
});