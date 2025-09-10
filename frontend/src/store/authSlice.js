// frontend/src/store/authSlice.js
export const createAuthSlice = (set, get) => ({
  jwtToken: localStorage.getItem('jwtToken') || null,
  isLoading: true, // Начинаем с true, чтобы показать загрузчик при первом входе

  login: (token) => {
    localStorage.setItem('jwtToken', token);
    set({ jwtToken: token });
  },

  logout: () => {
    localStorage.removeItem('jwtToken');
    // При выходе сбрасываем состояние пользователя и токен
    get().resetUserSlice(); 
    set({ jwtToken: null, isLoading: false });
  },

  finishInitialLoad: () => {
    set({ isLoading: false });
  },
});