// frontend/src/hooks/useFeatureFlag.js
// Rationale: Хук обновлен для получения данных из useCurrentUser, а не из Zustand.
// Это гарантирует, что флаги всегда соответствуют данным с сервера.
import { useCurrentUser } from './useCurrentUser';

export const useFeatureFlag = () => {
    const { data: currentUser } = useCurrentUser();
    const availableFeatures = currentUser?.available_features || [];

    const isFeatureAvailable = (featureKey) => {
        return availableFeatures.includes(featureKey);
    };

    return { isFeatureAvailable };
};