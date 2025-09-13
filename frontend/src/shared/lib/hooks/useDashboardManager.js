import { useState, useCallback } from 'react';
import { toast } from 'react-hot-toast';
import { runTask } from '@/shared/api/api';

const getErrorMessage = (error) => {
  if (typeof error?.response?.data?.detail === 'string') {
    return error.response.data.detail;
  }
  if (Array.isArray(error.response?.data?.detail)) {
    const firstError = error.response.data.detail[0];
    return `Ошибка валидации: ${firstError.loc.join('.')} - ${firstError.msg}`;
  }
  return error?.message || 'Произошла неизвестная ошибка.';
};

const cleanupParams = (params) => {
  const cleaned = JSON.parse(JSON.stringify(params));
  if (cleaned.filters) {
    if (cleaned.filters.last_seen_hours === 0) {
      cleaned.filters.last_seen_hours = null;
    }
    if (cleaned.filters.last_seen_days === 0) {
      cleaned.filters.last_seen_days = null;
    }
  }
  return cleaned;
};

export const useDashboardManager = () => {
  const [modalState, setModalState] = useState({
    open: false,
    title: '',
    actionKey: '',
  });

  const openModal = useCallback((key, title) => {
    setModalState({ open: true, actionKey: key, title: title });
  }, []);

  const closeModal = useCallback(() => {
    setModalState({ open: false, title: '', actionKey: '' });
  }, []);

  const handleActionSubmit = useCallback(
    async (actionKey, params) => {
      const currentTitle = modalState.title;
      const toastId = `task-queue-${actionKey}`;

      try {
        const apiParams = cleanupParams(params);
        toast.loading(`Задача "${currentTitle}" добавляется в очередь...`, {
          id: toastId,
        });
        await runTask(actionKey, apiParams);
        toast.success(`Задача "${currentTitle}" успешно добавлена в очередь!`, {
          id: toastId,
        });
      } catch (error) {
        const errorMessage = getErrorMessage(error);
        toast.error(errorMessage, { id: toastId });
      }
    },
    [modalState.title]
  );

  return {
    modalState,
    openModal,
    closeModal,
    onActionSubmit: handleActionSubmit,
  };
};
