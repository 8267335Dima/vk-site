// frontend/src/utils/planUtils.js
// --- КОНФИГ ДОСТУПА К ФИЧАМ НА ФРОНТЕНДЕ ---
// Это дублирует логику с бэкенда, что позволяет нам
// моментально реагировать в UI, не дожидаясь ответа от сервера.
const planFeatures = {
    'Базовый': [],
    'Plus': [],
    'PRO': ['proxy_management', 'scenarios'],
    'Expired': []
};

export const is_feature_available = (planName, featureKey) => {
    const features = planFeatures[planName] || [];
    return features.includes(featureKey);
}