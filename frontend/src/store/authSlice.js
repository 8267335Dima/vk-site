// frontend/src/store/authSlice.js

// Этот слайс теперь экспортирует ДВА объекта: состояние и действия.
export const createAuthSlice = (set, get) => ({
  // --- Состояние (State) ---
  jwtToken: localStorage.getItem('jwtToken') || null,
  isLoading: true, // Начинаем с true для начальной загрузки

  // --- Действия (Actions) ---
  actions: {
    login: (token) => {
      localStorage.setItem('jwtToken', token);
      set({ jwtToken: token });
    },
    logout: () => {
      localStorage.removeItem('jwtToken');
      // Вызываем действие из другого слайса для сброса данных пользователя
      get().actions.resetUserSlice(); 
      set({ jwtToken: null, isLoading: false });
    },
    finishInitialLoad: () => {
      set({ isLoading: false });
    },
  }
});