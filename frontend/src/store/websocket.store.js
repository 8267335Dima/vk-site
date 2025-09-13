// frontend/src/store/websocket.store.js
// Rationale: Логика WebSocket вынесена в отдельный слайс для лучшей организации кода.
export const createWebSocketSlice = (set) => ({
    connectionStatus: 'Соединение...',
    actions: {
        setConnectionStatus: (status) => set({ connectionStatus: status }),
    }
});