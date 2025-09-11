// frontend/src/hooks/useDashboardManager.js
import { useState, useCallback } from 'react';
import { toast } from 'react-hot-toast';
import { runTask } from 'api.js';

const getErrorMessage = (error) => {
    if (typeof error?.response?.data?.detail === 'string') {
        return error.response.data.detail;
    }
    return error?.message || "Произошла неизвестная ошибка.";
};

export const useDashboardManager = () => {
    const [modalState, setModalState] = useState({ open: false, title: '', actionKey: '' });

    // --- ИСПРАВЛЕНИЕ: Оборачиваем все функции в useCallback ---
    // Это гарантирует, что функции не будут пересоздаваться на каждом рендере,
    // предотвращая лишние перерисовки дочерних компонентов.
    const openModal = useCallback((key, title) => {
        setModalState({ open: true, actionKey: key, title: title });
    }, []);
    
    const closeModal = useCallback(() => {
        setModalState({ open: false, title: '', actionKey: '' });
    }, []);

    const handleActionSubmit = useCallback(async (actionKey, params) => {
        // Получаем title из состояния на момент вызова, а не из замыкания
        const currentTitle = modalState.title; 
        const toastId = `task-queue-${actionKey}`;
        
        try {
            toast.loading(`Задача "${currentTitle}" добавляется в очередь...`, { id: toastId });
            await runTask(actionKey, params);
            toast.success(`Задача "${currentTitle}" успешно добавлена в очередь!`, { id: toastId });
        } catch (error) {
            const errorMessage = getErrorMessage(error);
            toast.error(errorMessage, { id: toastId });
        }
    }, [modalState.title]); // Зависимость от modalState.title, чтобы в тосте было актуальное имя

    return {
        modalState,
        openModal,
        closeModal,
        onActionSubmit: handleActionSubmit,
    };
};