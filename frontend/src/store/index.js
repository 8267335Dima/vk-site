// frontend/src/store/index.js
// Rationale: Главный файл стора, который собирает все слайсы.
// Логика подписки на изменение токена для управления WebSocket соединением находится здесь.
import { create } from 'zustand';
import { createAuthSlice } from './auth.store';
import { createWebSocketSlice } from './websocket.store';
import { connectWebSocket, disconnectWebSocket } from '../websocket';

export const useStore = create((set, get) => {
    const authSlice = createAuthSlice(set, get);
    const webSocketSlice = createWebSocketSlice(set, get);

    return {
        ...authSlice,
        ...webSocketSlice,
        // Объединяем все actions в один объект для удобного доступа
        actions: {
            ...authSlice.actions,
            ...webSocketSlice.actions,
        },
    };
});

// Хук для удобного доступа к actions
export const useStoreActions = () => useStore(state => state.actions);

// Инициализация WebSocket соединения при загрузке приложения, если токен уже есть
const initialToken = useStore.getState().token;
if (initialToken) {
    connectWebSocket(initialToken);
}

// Подписка на изменение состояния токена
useStore.subscribe(
    (state, prevState) => {
        if (state.token && !prevState.token) {
            connectWebSocket(state.token);
        } else if (!state.token && prevState.token) {
            disconnectWebSocket();
            state.actions.setConnectionStatus('Отключено');
        }
    }
);