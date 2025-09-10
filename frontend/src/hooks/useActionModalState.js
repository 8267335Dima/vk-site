// frontend/src/hooks/useActionModalState.js
import { useState, useEffect, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchTaskInfo } from 'api';
import { useUserStore } from 'store/userStore';
import { toast } from 'react-hot-toast';
import { dashboardContent } from 'content/dashboardContent';

const { modal: content } = dashboardContent;

export const useActionModalState = (open, actionKey, title) => {
    const [params, setParams] = useState({});
    const userInfo = useUserStore(state => state.userInfo);
    const friendsCount = userInfo?.counters?.friends || 0;

    const { data: taskInfo, isLoading: isLoadingInfo } = useQuery({
        queryKey: ['taskInfo', actionKey],
        queryFn: () => fetchTaskInfo(actionKey),
        enabled: open && ['accept_friends', 'remove_friends'].includes(actionKey),
    });

    useEffect(() => {
        if (open) {
            const defaults = { ...content.defaults }; // Копируем, чтобы не мутировать оригинал
            if (actionKey === 'add_recommended') defaults.count = 20;
            if (actionKey === 'remove_friends') defaults.count = 500;
            setParams(defaults);
        }
    }, [open, actionKey]);
    
    // --- ИЗМЕНЕНИЕ: Основная функция для обработки всех изменений ---
    const handleParamChange = (name, value, type, checked) => {
        const val = type === 'checkbox' ? checked : value;

        if (name === 'count') {
            handleCountChange(val);
        } else if (Object.keys(content.defaults.filters).includes(name)) {
            setParams(p => ({ ...p, filters: { ...p.filters, [name]: val } }));
        } else if (Object.keys(content.defaults.like_config).includes(name)) {
            setParams(p => ({ ...p, like_config: { ...p.like_config, [name]: val } }));
        }
        else {
            setParams(p => ({ ...p, [name]: val }));
        }
    };
    
    // --- ИЗМЕНЕНИЕ: Логика ограничения ввода ---
    const handleCountChange = (value) => {
        let numericValue = parseInt(value, 10);
        if (isNaN(numericValue)) numericValue = 0;

        let limit = Infinity;
        let limitType = '';

        if (actionKey?.includes('add')) {
            limit = userInfo?.daily_add_friends_limit;
            limitType = 'заявок';
        } else if (actionKey?.includes('like')) {
            limit = userInfo?.daily_likes_limit;
            limitType = 'лайков';
        } else if (actionKey === 'remove_friends') {
            limit = friendsCount;
            limitType = 'друзей';
        }

        if (limit !== Infinity && numericValue > limit) {
            numericValue = limit;
            toast.info(`Максимальное значение для вас: ${limit} ${limitType}`);
        }
        setParams(p => ({ ...p, count: numericValue }));
    };

    const getModalTitle = useCallback(() => {
        let fullTitle = `${content.titlePrefix}: ${title}`;
        if (isLoadingInfo) {
            fullTitle += ' (Загрузка...)';
        } else if (taskInfo?.count !== undefined) {
            if (actionKey === 'accept_friends') fullTitle += ` (${taskInfo.count} заявок)`;
            if (actionKey === 'remove_friends') fullTitle += ` (${taskInfo.count} друзей)`;
        }
        return fullTitle;
    }, [title, actionKey, taskInfo, isLoadingInfo]);

    return { params, getModalTitle, handleParamChange };
};