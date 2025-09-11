// frontend/src/hooks/useDashboardManager.js
import { useState } from 'react';
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

    const openModal = (key, title) => setModalState({ open: true, actionKey: key, title: title });
    const closeModal = () => setModalState({ open: false, title: '', actionKey: '' });

    const handleActionSubmit = async (actionKey, params) => {
        try {
            toast.loading(`Задача "${modalState.title}" добавляется в очередь...`, { id: 'task-queue' });
            // --- ИЗМЕНЕНИЕ: Используем единую функцию runTask ---
            await runTask(actionKey, params);
            toast.success(`Задача "${modalState.title}" успешно добавлена в очередь!`, { id: 'task-queue' });
        } catch (error) {
            const errorMessage = getErrorMessage(error);
            toast.error(errorMessage, { id: 'task-queue' });
        }
    };

    return {
        modalState,
        openModal,
        closeModal,
        onActionSubmit: handleActionSubmit,
    };
};