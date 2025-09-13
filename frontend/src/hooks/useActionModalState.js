// frontend/src/hooks/useActionModalState.js
import { useState, useEffect, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchTaskInfo } from '../api';
import { useStore } from '../store';

export const useActionModalState = (open, actionKey, title) => {
    const [params, setParams] = useState({});
    const daily_add_friends_limit = useStore(state => state.userInfo?.daily_add_friends_limit);
    const daily_likes_limit = useStore(state => state.userInfo?.daily_likes_limit);

    const { data: taskInfo, isLoading: isLoadingInfo } = useQuery({
        queryKey: ['taskInfo', actionKey],
        queryFn: () => fetchTaskInfo(actionKey),
        enabled: !!(open && actionKey),
        staleTime: 1000 * 60 * 5,
    });

    useEffect(() => {
        if (open) {
            const defaults = {
                count: 50,
                filters: { sex: 0, is_online: false, allow_closed_profiles: false, remove_banned: true, min_friends: null, max_friends: null, min_followers: null, max_followers: null, last_seen_hours: 0, last_seen_days: 0 },
                like_config: { enabled: false, targets: ['avatar'] },
                send_message_on_add: false,
                message_text: "Привет, {name}! Увидел(а) твой профиль в рекомендациях, буду рад(а) знакомству.",
                only_new_dialogs: false,
            };
            if (actionKey === 'add_recommended') defaults.count = 20;
            if (actionKey === 'remove_friends') defaults.count = 500;
            setParams(defaults);
        }
    }, [open, actionKey]);
    
    const handleParamChange = useCallback((name, value) => {
        setParams(p => {
            const keys = name.split('.');
            if (keys.length > 1) {
                const newParams = { ...p };
                let current = newParams;
                for (let i = 0; i < keys.length - 1; i++) {
                    current[keys[i]] = { ...current[keys[i]] };
                    current = current[keys[i]];
                }
                current[keys[keys.length - 1]] = value;
                return newParams;
            }
            return { ...p, [name]: value };
        });
    }, []);
    
    const getModalTitle = useCallback(() => {
        let fullTitle = title;
        if (isLoadingInfo) {
            fullTitle += ' (Загрузка...)';
        } else if (taskInfo?.count !== undefined) {
            if (actionKey === 'accept_friends') fullTitle += ` (${taskInfo.count} заявок)`;
            if (actionKey === 'remove_friends') fullTitle += ` (${taskInfo.count} друзей)`;
        }
        return fullTitle;
    }, [title, actionKey, taskInfo, isLoadingInfo]);

    const getActionLimit = useCallback(() => {
        if (actionKey?.includes('add')) return daily_add_friends_limit || 100;
        if (actionKey?.includes('like')) return daily_likes_limit || 1000;
        if (actionKey === 'remove_friends') return taskInfo?.count || 1000;
        if (actionKey === 'mass_messaging') return 500;
        return 1000;
    }, [actionKey, daily_add_friends_limit, daily_likes_limit, taskInfo]);

    return { params, getModalTitle, handleParamChange, getActionLimit };
};