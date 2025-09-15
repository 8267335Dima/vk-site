import { create } from 'zustand';
import { createAuthSlice } from './auth.store';
import { createWebSocketSlice } from './websocket.store';
import { connectWebSocket, disconnectWebSocket } from '@/shared/api/websocket';

export const useStore = create((set, get) => {
  const authSlice = createAuthSlice(set, get);
  const webSocketSlice = createWebSocketSlice(set, get);

  return {
    ...authSlice,
    ...webSocketSlice,
    actions: {
      ...authSlice.actions,
      ...webSocketSlice.actions,
    },
  };
});

export const useStoreActions = () => useStore((state) => state.actions);

const initialToken = useStore.getState().token;
if (initialToken) {
  connectWebSocket(initialToken);
}

useStore.subscribe((state, prevState) => {
  if (state.token && !prevState.token) {
    connectWebSocket(state.token);
  } else if (!state.token && prevState.token) {
    disconnectWebSocket();
    state.actions.setConnectionStatus('Отключено');
  }
});
