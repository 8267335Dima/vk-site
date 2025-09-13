// frontend/src/store/userSlice.js
const initialState = {
    // В будущем здесь может быть состояние, не связанное с сервером,
    // например, тема оформления (light/dark), состояние открытых панелей и т.д.
};

export const createUserSlice = (set) => ({
    ...initialState,

    actions: {
        // Эта функция теперь не нужна, так как загрузка данных
        // происходит через хуки useQuery в компонентах.
        // loadUser: async () => { ... } // УДАЛЕНО

        resetUserSlice: () => set(initialState),
    }
});