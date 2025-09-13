// frontend/src/hooks/useCurrentUser.js
// Rationale: Это сердце новой архитектуры. Единственный источник правды для данных текущего пользователя.
// Он не только предоставляет данные, но и синхронизирует состояние аутентификации в Zustand
// при получении ошибки 401, делая систему самовосстанавливающейся.
import { useQuery } from '@tanstack/react-query';
import { fetchUserInfo } from 'api';
import { useStore } from 'store';

export const useCurrentUser = () => {
    const token = useStore(state => state.token);
    const activeProfileId = useStore(state => state.activeProfileId);
    const { setUnauthenticated } = useStore(state => state.actions);

    return useQuery({
        // Ключ запроса теперь включает ID активного профиля,
        // React Query автоматически перезагрузит данные при его смене.
        queryKey: ['currentUser', activeProfileId],
        queryFn: fetchUserInfo,
        enabled: !!token, // Запрос выполняется только при наличии токена
        staleTime: 1000 * 60 * 15, // 15 минут "свежести" данных
        gcTime: 1000 * 60 * 30, // 30 минут жизни в кэше
        select: (response) => response.data,
        retry: false, // Не повторять запрос при ошибке, т.к. это скорее всего 401
        onError: (error) => {
            if (error.response?.status === 401) {
                // Если токен невалиден, выходим из системы
                setUnauthenticated();
            }
        },
    });
};