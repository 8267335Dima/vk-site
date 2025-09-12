// frontend/src/store/userStore.js
import { create } from 'zustand';
import { createAuthSlice } from './authSlice';
import { createUserSlice } from './userSlice';
import { connectWebSocket, disconnectWebSocket } from '../websocket';

const createWebSocketSlice = (set) => ({
    connectionStatus: 'Соединение...',
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
    
    delete combinedState.actions.actions;

    return combinedState;
});

export const useUserActions = () => useUserStore(state => state.actions);

useUserStore.subscribe(
    (state, prevState) => {
        if (state.jwtToken && !prevState.jwtToken) {
            connectWebSocket(state.jwtToken);
        } else if (!state.jwtToken && prevState.jwtToken) {
            disconnectWebSocket();
        }
    }
);

const initialToken = useUserStore.getState().jwtToken;
if (initialToken) {
    connectWebSocket(initialToken);
}