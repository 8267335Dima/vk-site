// frontend/src/hooks/useActionTask.js
// Rationale: Этот хук инкапсулирует всю логику выполнения задачи:
// отображение toast-уведомлений, вызов API, обработка успеха и ошибок.
// Компоненты теперь просто вызывают `mutate(params)`.
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { runTask } from 'api';
import { toast } from 'react-hot-toast';

const getErrorMessage = (error) => {
    if (typeof error?.response?.data?.detail === 'string') {
        return error.response.data.detail;
    }
    return error?.message || "Произошла неизвестная ошибка.";
};

export const useActionTask = (actionKey, title, onSuccessCallback) => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (params) => runTask(actionKey, params),
        onMutate: () => {
            // Оптимистичное обновление или просто показ лоадера
            return toast.loading(`Задача "${title}" добавляется в очередь...`);
        },
        onSuccess: (data, variables, toastId) => {
            toast.success(`Задача "${title}" успешно добавлена!`, { id: toastId });
            // Инвалидируем историю задач, чтобы она обновилась
            queryClient.invalidateQueries({ queryKey: ['task_history'] });
            if (onSuccessCallback) onSuccessCallback();
        },
        onError: (error, variables, toastId) => {
            const errorMessage = getErrorMessage(error);
            toast.error(errorMessage, { id: toastId });
        },
    });
};