// frontend/src/hooks/useFeatureFlag.js
import { useUserStore } from 'store/userStore';

/**
 * Хук для проверки доступности фич на основе данных, полученных с бэкенда.
 * @returns {{isFeatureAvailable: (featureKey: string) => boolean}}
 */
export const useFeatureFlag = () => {
    const availableFeatures = useUserStore(state => state.availableFeatures);

    const isFeatureAvailable = (featureKey) => {
        return availableFeatures.includes(featureKey);
    };

    return { isFeatureAvailable };
};