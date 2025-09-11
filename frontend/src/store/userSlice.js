// frontend/src/store/userSlice.js
import { fetchUserInfo } from 'api';

const initialState = {
    userInfo: null,
    availableFeatures: [], 
};

export const createUserSlice = (set, get) => ({
    ...initialState,

    actions: {
        loadUser: async () => {
            if (!get().jwtToken) {
                return get().actions.finishInitialLoad();
            }
            
            try {
                const userResponse = await fetchUserInfo();
                set({
                    userInfo: userResponse.data,
                    availableFeatures: userResponse.data.available_features || [],
                });
            } catch (error) {
                console.error("Failed to load user data, logging out.", error);
                get().actions.logout(); 
            } finally {
                get().actions.finishInitialLoad();
            }
        },
        
        setUserInfo: (newUserInfo) => {
            set(state => ({
                userInfo: {
                    ...state.userInfo,
                    ...newUserInfo,
                }
            }));
        },
        
        resetUserSlice: () => set(initialState),
    }
});