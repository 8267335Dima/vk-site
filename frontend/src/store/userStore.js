// frontend/src/store/userStore.js
import { create } from 'zustand';
import { createAuthSlice } from './authSlice';
import { createUserSlice } from './userSlice';

// --- ИЗМЕНЕНИЕ: Структура хранилища переработана для стабильности селекторов ---
export const useUserStore = create((set, get) => {
  // Создаем временные экземпляры слайсов, чтобы извлечь из них состояния и действия
  const authSlice = createAuthSlice(set, get);
  const userSlice = createUserSlice(set, get);

  return {
    // Собираем все состояния из всех слайсов
    ...authSlice,
    ...userSlice,
    
    // Собираем все действия в одно стабильное поле 'actions'
    // Это гарантирует, что объект `actions` не пересоздается при каждом вызове `create`
    actions: {
      ...authSlice.actions,
      ...userSlice.actions,
    },

    // Удаляем вложенные `actions` из корневого уровня, чтобы избежать дублирования
    // и путаницы. Теперь доступ к действиям есть только через `state.actions`.
    ...(() => {
        delete authSlice.actions;
        delete userSlice.actions;
        return { ...authSlice, ...userSlice };
    })(),
  };
});

// --- НОВЫЙ СЕЛЕКТОР: Для удобного и безопасного доступа только к действиям ---
// Этот хук всегда будет возвращать один и тот же объект с функциями,
// что делает его идеальным для использования в `useEffect` без лишних срабатываний.
export const useUserActions = () => useUserStore(state => state.actions);