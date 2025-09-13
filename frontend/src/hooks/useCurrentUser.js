// frontend/src/hooks/useCurrentUser.js
import { useQuery } from '@tanstack/react-query';
import { fetchUserInfo } from 'api';
import { useUserStore } from 'store/userStore';

export const useCurrentUser = () => {
    const jwtToken = useUserStore(state => state.jwtToken);
    
    return useQuery({
        // Ключ запроса включает ID профиля, чтобы данные автоматически перезагружались при смене профиля
        queryKey: ['currentUser', useUserStore.getState().activeProfileId],
        queryFn: fetchUserInfo,
        // Запрос активен только если есть токен
        enabled: !!jwtToken,
        // Данные о пользователе (имя, тариф) не меняются очень часто,
        // поэтому можно установить большое время "свежести" данных.
        // React Query все равно может обновить их в фоне при необходимости.
        staleTime: 1000 * 60 * 15, // 15 минут
        // Данные не удаляются из кэша сразу, даже если компонент размонтирован.
        gcTime: 1000 * 60 * 30, // 30 минут
        // Выбираем только сам объект с данными для удобства
        select: (response) => response.data,
        // Не повторять запрос при ошибке, так как это скорее всего 401,
        // и обработка выхода из системы произойдет в PrivateRoutes.
        retry: false,
    });
};