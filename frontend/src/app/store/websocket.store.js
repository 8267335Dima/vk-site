export const createWebSocketSlice = (set) => ({
  connectionStatus: 'Соединение...',
  actions: {
    setConnectionStatus: (status) => set({ connectionStatus: status }),
  },
});
