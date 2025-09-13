// frontend/src/websocket.js
import { toast } from 'react-hot-toast';
import { useStore } from './store';
import { queryClient } from './queryClient';

let socket = null;
let reconnectInterval = 5000;
let reconnectTimeout = null;

const getSocketUrl = () => {
    const apiUrl = process.env.REACT_APP_API_BASE_URL || window.location.origin;
    const wsUrl = new URL(apiUrl);
    wsUrl.protocol = wsUrl.protocol.replace('http', 'ws');
    wsUrl.pathname = '/api/v1/ws';
    return wsUrl.toString();
};

const handleMessage = (event) => {
    try {
        const { type, payload } = JSON.parse(event.data);
        const { setDailyLimits } = useStore.getState().actions;

        switch (type) {
            case 'log':
                console.log('WS Log:', payload);
                break;
            case 'stats_update':
                setDailyLimits({
                    likes_today: payload.likes_count,
                    friends_add_today: payload.friends_added_count
                });
                break;
            case 'task_history_update':
                queryClient.setQueryData(['task_history'], (oldData) => {
                    if (!oldData) return oldData;
                    
                    const newPages = oldData.pages.map(page => ({
                        ...page,
                        items: page.items.map(task => 
                            task.id === payload.task_history_id 
                                ? { ...task, status: payload.status, result: payload.result } 
                                : task
                        )
                    }));

                    return { ...oldData, pages: newPages };
                });

                if (payload.status === 'SUCCESS') {
                    toast.success(`Задача "${payload.task_name}" успешно завершена!`);
                }
                if (payload.status === 'FAILURE') {
                    toast.error(`Задача "${payload.task_name}" провалена: ${payload.result}`, { duration: 8000 });
                }
                break;
            case 'new_notification':
                queryClient.invalidateQueries({ queryKey: ['notifications'] });
                const message = payload.message;
                const options = { duration: 8000 };
                if (payload.level === 'error') toast.error(message, options);
                else if (payload.level === 'warning') toast.error(message, options);
                else toast.success(message, { duration: 5000 });
                break;
            default:
                break;
        }
    } catch (error) {
        console.error("Error parsing WebSocket message:", error);
    }
};

export const connectWebSocket = (token) => {
    if (socket || !token) return;

    const url = `${getSocketUrl()}?token=${token}`;
    socket = new WebSocket(url);

    socket.onopen = () => {
        console.log('WebSocket connected');
        useStore.getState().actions.setConnectionStatus('На связи');
        if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };

    socket.onclose = (event) => {
        console.log(`WebSocket disconnected: ${event.code}`);
        socket = null;
        useStore.getState().actions.setConnectionStatus('Переподключение...');
        
        const currentToken = useStore.getState().jwtToken;
        if (currentToken) {
           reconnectTimeout = setTimeout(() => connectWebSocket(currentToken), reconnectInterval);
        }
    };

    socket.onerror = (error) => {
        console.error('WebSocket error:', error);
        // <-- ИЗМЕНЕНИЕ: Добавлена проверка, чтобы избежать ошибки
        if (socket) {
            socket.close();
        }
    };

    socket.onmessage = handleMessage;
};

export const disconnectWebSocket = () => {
    if (reconnectTimeout) clearTimeout(reconnectTimeout);
    if (socket) {
        socket.close();
        socket = null;
        useStore.getState().actions.setConnectionStatus('Отключено');
    }
};