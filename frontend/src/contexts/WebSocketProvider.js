// frontend/src/contexts/WebSocketProvider.js
import React, { createContext, useState, useEffect, useMemo, useCallback, useContext } from 'react';
import useWebSocket, { ReadyState } from 'react-use-websocket';
import { toast } from 'react-hot-toast';
import { useQueryClient } from '@tanstack/react-query';
// --- ИСПРАВЛЕНИЕ: Используем хук для получения стабильных действий ---
import { useUserStore, useUserActions } from 'store/userStore';

export const WebSocketContext = createContext(null);

export const useWebSocketContext = () => {
    return useContext(WebSocketContext);
};

export const WebSocketProvider = ({ children }) => {
    const queryClient = useQueryClient();
    const jwtToken = useUserStore(state => state.jwtToken);
    // --- ИСПРАВЛЕНИЕ: Получаем действие через стабильный хук ---
    const { setUserInfo } = useUserActions(); 
    
    const [logs, setLogs] = useState([]);
    const [taskHistory, setTaskHistory] = useState({});

    const socketUrl = useMemo(() => {
        if (!jwtToken) return null;
        const location = window.location;
        const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsHost = process.env.NODE_ENV === 'development' ? 'localhost:8000' : location.host;
        return `${wsProtocol}//${wsHost}/api/v1/ws`;
    }, [jwtToken]);
    
    const socketOptions = useMemo(() => ({
        protocols: jwtToken ? ['bearer', jwtToken] : undefined,
        shouldReconnect: (closeEvent) => !!jwtToken,
        reconnectInterval: 5000,
    }), [jwtToken]);

    const { lastJsonMessage, readyState } = useWebSocket(socketUrl, socketOptions);
    
    // --- ИСПРАВЛЕНИЕ: Оборачиваем обработчик в useCallback для стабильности ---
    const handleTaskHistoryUpdate = useCallback((payload) => {
        setTaskHistory(prev => ({ ...prev, [payload.task_history_id]: payload }));
        if (payload.status === 'SUCCESS') {
            toast.success(`Задача успешно завершена!`, { duration: 5000 });
        }
        if (payload.status === 'FAILURE') {
            toast.error(`Задача провалена: ${payload.result}`, { duration: 8000 });
        }
        queryClient.invalidateQueries({ queryKey: ['task_history'] });
    }, [queryClient]);

    // --- ИСПРАВЛЕНИЕ: Оборачиваем обработчик в useCallback для стабильности ---
    const handleNewNotification = useCallback((payload) => {
        const message = payload.message;
        if (payload.level === 'error') {
            toast.error(message, { duration: 8000 });
            queryClient.invalidateQueries({ queryKey: ['automations'] });
            queryClient.invalidateQueries({ queryKey: ['scenarios'] });
        } else {
            toast.success(message, { duration: 5000 });
        }
        queryClient.invalidateQueries({ queryKey: ['notifications'] });
    }, [queryClient]);

    // --- ИСПРАВЛЕНИЕ: Оборачиваем обработчик в useCallback для стабильности ---
    const handleStatsUpdate = useCallback((payload) => {
        // Обновляем userInfo, добавляя или обновляя счетчики
        setUserInfo({ counters: payload });
    }, [setUserInfo]);

    useEffect(() => {
        if (lastJsonMessage !== null) {
            const { type, payload } = lastJsonMessage;
            
            switch (type) {
                case 'log':
                    setLogs(prev => [payload, ...prev.slice(0, 199)]);
                    break;
                case 'stats_update':
                    handleStatsUpdate(payload);
                    break;
                case 'task_history_update':
                    handleTaskHistoryUpdate(payload);
                    break;
                case 'new_notification':
                    handleNewNotification(payload);
                    break;
                default:
                    break;
            }
        }
    }, [lastJsonMessage, handleStatsUpdate, handleTaskHistoryUpdate, handleNewNotification]);

    const connectionStatus = useMemo(() => ({
        [ReadyState.CONNECTING]: 'Подключение...',
        [ReadyState.OPEN]: 'Live',
        [ReadyState.CLOSING]: 'Завершение',
        [ReadyState.CLOSED]: 'Отключено',
        [ReadyState.UNINSTANTIATED]: 'Не подключено',
    }[readyState]), [readyState]);

    const value = useMemo(() => ({
        logs,
        connectionStatus,
        taskHistory,
    }), [logs, connectionStatus, taskHistory]);

    return (
        <WebSocketContext.Provider value={value}>
            {children}
        </WebSocketContext.Provider>
    );
};