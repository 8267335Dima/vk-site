// frontend/src/store/userSlice.js
import { fetchUserInfo, fetchActivityStats } from 'api.js';

const initialStats = {
    likes_count: 0,
    friends_added_count: 0,
    friend_requests_accepted_count: 0,
};

const initialState = {
    userInfo: null,
    dailyStats: initialStats,
    // --- НОВОЕ ПОЛЕ ---
    availableFeatures: [], 
};

export const createUserSlice = (set, get) => ({
    ...initialState,

    loadUser: async () => {
        if (!get().jwtToken) {
            return get().finishInitialLoad();
        }
        
        try {
            const userResponse = await fetchUserInfo();
            const statsData = await fetchActivityStats(1);
            const todayStats = statsData.data[0];

            set({
                userInfo: userResponse.data,
                // --- НОВОЕ ПОЛЕ ---
                availableFeatures: userResponse.data.available_features || [],
                dailyStats: todayStats ? {
                    likes_count: todayStats.likes,
                    friends_added_count: todayStats.friends_added,
                    friend_requests_accepted_count: todayStats.requests_accepted,
                } : initialStats,
            });
        } catch (error) {
            console.error("Failed to load user, logging out.", error);
            get().logout(); 
        } finally {
            get().finishInitialLoad();
        }
    },
    
    updateDailyStats: (statKey, value) => {
        set(state => ({
            dailyStats: {
                ...state.dailyStats,
                [statKey]: value
            }
        }));
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
});