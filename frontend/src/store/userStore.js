// frontend/src/store/userStore.js
import { create } from 'zustand';
import { createAuthSlice } from './authSlice';
import { createUserSlice } from './userSlice';

export const useUserStore = create((set, get) => {
  const authSlice = createAuthSlice(set, get);
  const userSlice = createUserSlice(set, get);

  const combinedState = {
    ...authSlice,
    ...userSlice,
    actions: {
      ...authSlice.actions,
      ...userSlice.actions,
    },
  };

  delete combinedState.actions.actions;
  delete combinedState.authSlice;
  delete combinedState.userSlice;

  return combinedState;
});

export const useUserActions = () => useUserStore(state => state.actions);