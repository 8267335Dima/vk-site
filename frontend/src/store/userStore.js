// frontend/src/store/userStore.js

import { create } from 'zustand';
import { createAuthSlice } from './authSlice';
import { createUserSlice } from './userSlice';
import { connectWebSocket, disconnectWebSocket } from '../websocket'; // <-- НОВЫЙ ИМПОРТ

// Добавляем новый slice для управления состоянием WebSocket
const createWebSocketSlice = (set) => ({
    connectionStatus: 'Не подключено',
    actions: {
        setConnectionStatus: (status) => set({ connectionStatus: status }),
    }
});

export const useUserStore = create((set, get) => {
    const authSlice = createAuthSlice(set, get);
    const userSlice = createUserSlice(set, get);
    const webSocketSlice = createWebSocketSlice(set, get);

    const combinedState = {
        ...authSlice,
        ...userSlice,
        ...webSocketSlice,
        actions: {
            ...authSlice.actions,
            ...userSlice.actions,
            ...webSocketSlice.actions,
        },
    };
    
    // Удаляем вложенные 'actions', чтобы все было на одном уровне
    delete combinedState.actions.actions;

    return combinedState;
});

export const useUserActions = () => useUserStore(state => state.actions);

// --- КЛЮЧЕВАЯ ЛОГИКА ---
// Подписываемся на изменения токена в store.
// Как только токен появляется - подключаемся. Как только исчезает - отключаемся.
useUserStore.subscribe(
    (state, prevState) => {
        if (state.jwtToken && !prevState.jwtToken) {
            connectWebSocket(state.jwtToken);
        } else if (!state.jwtToken && prevState.jwtToken) {
            disconnectWebSocket();
        }
    }
);

// Первоначальное подключение при загрузке страницы, если токен уже есть
const initialToken = useUserStore.getState().jwtToken;
if (initialToken) {
    connectWebSocket(initialToken);
}