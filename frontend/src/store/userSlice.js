// frontend/src/store/userSlice.js
import { fetchUserInfo, fetchUserLimits } from 'api';

const initialState = {
    userInfo: null,
    availableFeatures: [], 
    dailyLimits: {
        likes_limit: 0,
        likes_today: 0,
        friends_add_limit: 0,
        friends_add_today: 0,
    }
};

export const createUserSlice = (set, get) => ({
    ...initialState,

    actions: {
        loadUser: async () => {
            if (!get().jwtToken) {
                return get().actions.finishInitialLoad();
            }
            
            try {
                const [userResponse, limitsResponse] = await Promise.all([
                    fetchUserInfo(),
                    fetchUserLimits()
                ]);

                set({
                    userInfo: userResponse.data,
                    availableFeatures: userResponse.data.available_features || [],
                    dailyLimits: limitsResponse.data,
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
                userInfo: { ...state.userInfo, ...newUserInfo }
            }));
        },

        setDailyLimits: (newLimits) => {
             set(state => ({
                dailyLimits: { ...state.dailyLimits, ...newLimits }
            }));
        },
        
        resetUserSlice: () => set(initialState),
    }
});