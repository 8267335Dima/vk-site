// frontend/src/store/userSlice.js
import { fetchUserInfo } from 'api.js';

const initialState = {
    userInfo: null,
    availableFeatures: [], 
};

// Аналогично, разделяем состояние и действия.
export const createUserSlice = (set, get) => ({
    // --- Состояние (State) ---
    ...initialState,

    // --- Действия (Actions) ---
    actions: {
        loadUser: async () => {
            // Используем get() для доступа к токену из authSlice
            if (!get().jwtToken) {
                // Вызываем действие из authSlice
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
                // Если загрузка не удалась (например, токен истек), выходим из системы
                get().actions.logout(); 
            } finally {
                // В любом случае завершаем начальную загрузку
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
        
        // Действие для сброса этого слайса к начальному состоянию
        resetUserSlice: () => set(initialState),
    }
});