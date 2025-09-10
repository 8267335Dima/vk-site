// frontend/src/contexts/WebSocketProvider.js
import React, { createContext, useState, useEffect, useMemo, useCallback, useContext } from 'react';
import useWebSocket, { ReadyState } from 'react-use-websocket';
import { toast } from 'react-hot-toast';
import { useQueryClient } from '@tanstack/react-query';
import { useUserStore } from 'store/userStore';

// 1. Создаем контекст
export const WebSocketContext = createContext(null);

// 2. Создаем кастомный хук для удобного и безопасного доступа к контексту
export const useWebSocketContext = () => {
    // useContext может вернуть null, если компонент находится вне провайдера
    return useContext(WebSocketContext);
};

// 3. Создаем компонент-провайдер, который будет оборачивать наше приложение
export const WebSocketProvider = ({ children }) => {
    const queryClient = useQueryClient();
    const jwtToken = useUserStore(state => state.jwtToken);
    const updateDailyStats = useUserStore(state => state.updateDailyStats);
    
    // Хранилища для данных, получаемых по WebSocket
    const [logs, setLogs] = useState([]);
    const [taskHistory, setTaskHistory] = useState({});

    // Формируем URL для WebSocket-соединения.
    // useMemo гарантирует, что URL будет пересчитан только при изменении токена.
    const socketUrl = useMemo(() => {
        if (!jwtToken) return null;
        const location = window.location;
        const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsHost = process.env.NODE_ENV === 'production' 
    ? location.host 
    : 'localhost'; // В режиме разработки всегда используем localhost:80
        return `${wsProtocol}//${wsHost}/api/v1/ws`;
    }, [jwtToken]);
    
    // Настройки для WebSocket-соединения, включая передачу JWT в subprotocol для аутентификации.
    const socketOptions = useMemo(() => ({
        protocols: jwtToken ? ['bearer', jwtToken] : undefined,
        shouldReconnect: (closeEvent) => !!jwtToken, // Переподключаться, только если пользователь авторизован
        reconnectInterval: 5000, // Попытка переподключения каждые 5 секунд
    }), [jwtToken]);

    // Основной хук, который управляет WebSocket-соединением
    const { lastJsonMessage, readyState } = useWebSocket(socketUrl, socketOptions);
    
    // Обработчик обновлений истории задач
    const handleTaskHistoryUpdate = useCallback((payload) => {
        setTaskHistory(prev => ({ ...prev, [payload.task_history_id]: payload }));
        if (payload.status === 'SUCCESS') {
            toast.success(`Задача успешно завершена!`, { duration: 5000 });
        }
        if (payload.status === 'FAILURE') {
            toast.error(`Задача провалена: ${payload.result}`, { duration: 8000 });
        }
        // Обновляем данные в React Query, чтобы страница истории обновилась
        queryClient.invalidateQueries({ queryKey: ['task_history'] });
    }, [queryClient]);

    // Обработчик новых уведомлений
    const handleNewNotification = useCallback((payload) => {
        const message = payload.message;
        if (payload.level === 'error') {
            toast.error(message, { duration: 8000 });
            // Если пришла ошибка (например, невалидный токен), обновляем данные по автоматизациям
            queryClient.invalidateQueries({ queryKey: ['automations'] });
            queryClient.invalidateQueries({ queryKey: ['scenarios'] });
        } else {
            toast.success(message, { duration: 5000 });
        }
        queryClient.invalidateQueries({ queryKey: ['notifications'] });
    }, [queryClient]);

    // useEffect для обработки всех входящих сообщений
    useEffect(() => {
        if (lastJsonMessage !== null) {
            const { type, payload } = lastJsonMessage;
            
            switch (type) {
                case 'log':
                    // Добавляем новый лог в начало массива, ограничивая его размер
                    setLogs(prev => [payload, ...prev.slice(0, 199)]);
                    break;
                case 'stats_update':
                    updateDailyStats(payload.stat, payload.value);
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
    }, [lastJsonMessage, updateDailyStats, handleTaskHistoryUpdate, handleNewNotification]);

    // Преобразуем числовой статус соединения в человекочитаемый текст
    const connectionStatus = useMemo(() => ({
        [ReadyState.CONNECTING]: 'Подключение...',
        [ReadyState.OPEN]: 'Live',
        [ReadyState.CLOSING]: 'Завершение',
        [ReadyState.CLOSED]: 'Отключено',
        [ReadyState.UNINSTANTIATED]: 'Не подключено',
    }[readyState]), [readyState]);

    // Формируем объект `value`, который будет доступен всем дочерним компонентам
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