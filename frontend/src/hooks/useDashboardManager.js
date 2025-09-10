// frontend/src/hooks/useDashboardManager.js
import { useState } from 'react';
import { toast } from 'react-hot-toast';
import {
  runAcceptFriends,
  runLikeFeed,
  runAddRecommended,
  runViewStories,
  runRemoveFriends,
  runLikeFriendsFeed
} from 'api';

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
        const actionMap = {
            'accept_friends': runAcceptFriends,
            'like_feed': runLikeFeed,
            'add_recommended': runAddRecommended,
            'view_stories': runViewStories,
            'remove_friends': runRemoveFriends,
            'like_friends_feed': runLikeFriendsFeed,
        };

        const taskFunction = actionMap[actionKey];
        if (!taskFunction) {
            toast.error(`Неизвестное действие: ${actionKey}`);
            return;
        }

        try {
            toast.loading(`Задача "${modalState.title}" добавляется в очередь...`, { id: 'task-queue' });
            await taskFunction(params);
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