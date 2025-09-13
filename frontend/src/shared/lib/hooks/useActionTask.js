import { useMutation, useQueryClient } from '@tanstack/react-query';
import { runTask } from '@/shared/api/api';
import { toast } from 'react-hot-toast';

const getErrorMessage = (error) => {
  if (typeof error?.response?.data?.detail === 'string') {
    return error.response.data.detail;
  }
  return error?.message || 'Произошла неизвестная ошибка.';
};

export const useActionTask = (actionKey, title, onSuccessCallback) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params) => runTask(actionKey, params),
    onMutate: () => {
      return toast.loading(`Задача "${title}" добавляется в очередь...`);
    },
    onSuccess: (data, variables, toastId) => {
      toast.success(`Задача "${title}" успешно добавлена!`, { id: toastId });
      queryClient.invalidateQueries({ queryKey: ['task_history'] });
      if (onSuccessCallback) onSuccessCallback();
    },
    onError: (error, variables, toastId) => {
      const errorMessage = getErrorMessage(error);
      toast.error(errorMessage, { id: toastId });
    },
  });
};
