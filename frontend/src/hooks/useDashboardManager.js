// frontend/src/hooks/useDashboardManager.js
import { useState, useCallback } from 'react';
import { toast } from 'react-hot-toast';
import { runTask } from '../api';

const getErrorMessage = (error) => {
    if (typeof error?.response?.data?.detail === 'string') {
        return error.response.data.detail;
    }
    // --- ИЗМЕНЕНИЕ: Добавлена проверка на ошибки валидации ---
    if (Array.isArray(error.response?.data?.detail)) {
        // Берем первую ошибку валидации для простоты
        const firstError = error.response.data.detail[0];
        return `Ошибка валидации: ${firstError.loc.join('.')} - ${firstError.msg}`;
    }
    return error?.message || "Произошла неизвестная ошибка.";
};

// --- НОВАЯ ФУНКЦИЯ-ХЕЛПЕР ---
// Эта функция преобразует параметры в формат, который ожидает API.
const cleanupParams = (params) => {
    // Создаем глубокую копию, чтобы не изменять оригинальный стейт
    const cleaned = JSON.parse(JSON.stringify(params));

    if (cleaned.filters) {
        // Если для фильтра "last_seen_hours" установлено значение 0 ("Неважно"),
        // мы устанавливаем его в null, как того требует Pydantic-схема на бэкенде.
        if (cleaned.filters.last_seen_hours === 0) {
            cleaned.filters.last_seen_hours = null;
        }
        // То же самое для "last_seen_days".
        if (cleaned.filters.last_seen_days === 0) {
            cleaned.filters.last_seen_days = null;
        }
    }
    return cleaned;
};


export const useDashboardManager = () => {
    const [modalState, setModalState] = useState({ open: false, title: '', actionKey: '' });

    const openModal = useCallback((key, title) => {
        setModalState({ open: true, actionKey: key, title: title });
    }, []);
    
    const closeModal = useCallback(() => {
        setModalState({ open: false, title: '', actionKey: '' });
    }, []);

    const handleActionSubmit = useCallback(async (actionKey, params) => {
        const currentTitle = modalState.title; 
        const toastId = `task-queue-${actionKey}`;
        
        try {
            // --- ИЗМЕНЕНИЕ: Очищаем параметры перед отправкой ---
            const apiParams = cleanupParams(params);
            
            toast.loading(`Задача "${currentTitle}" добавляется в очередь...`, { id: toastId });
            await runTask(actionKey, apiParams); // Отправляем очищенные параметры
            toast.success(`Задача "${currentTitle}" успешно добавлена в очередь!`, { id: toastId });
        } catch (error) {
            const errorMessage = getErrorMessage(error);
            toast.error(errorMessage, { id: toastId });
        }
    }, [modalState.title]);

    return {
        modalState,
        openModal,
        closeModal,
        onActionSubmit: handleActionSubmit,
    };
};