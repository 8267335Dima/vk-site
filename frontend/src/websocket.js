// frontend/src/websocket.js

import { toast } from 'react-hot-toast';
import { useUserStore } from 'store/userStore';

let socket = null;
let reconnectInterval = 5000;

const getSocketUrl = () => {
    const location = window.location;
    const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = location.host;
    return `${wsProtocol}//${wsHost}/api/v1/ws`;
};

const handleMessage = (event) => {
    const { type, payload } = JSON.parse(event.data);
    const { setUserInfo } = useUserStore.getState().actions;

    switch (type) {
        case 'log':
            // Эту логику можно будет потом перенести в store, если нужно
            console.log('WS Log:', payload);
            break;
        case 'stats_update':
            // Обновляем userInfo в store
            setUserInfo({ counters: payload });
            break;
        case 'task_history_update':
            if (payload.status === 'SUCCESS') {
                toast.success('Задача успешно завершена!', { duration: 5000 });
            }
            if (payload.status === 'FAILURE') {
                toast.error(`Задача провалена: ${payload.result}`, { duration: 8000 });
            }
            // Здесь можно добавить обновление истории задач в store, если потребуется
            break;
        case 'new_notification':
            const message = payload.message;
            if (payload.level === 'error') {
                toast.error(message, { duration: 8000 });
                // Можно добавить инвалидацию запросов, если нужно
            } else {
                toast.success(message, { duration: 5000 });
            }
            break;
        default:
            break;
    }
};

export const connectWebSocket = (token) => {
    if (socket || !token) {
        return;
    }

    const url = getSocketUrl();
    socket = new WebSocket(url, ['bearer', token]);

    socket.onopen = () => {
        console.log('WebSocket connected');
        useUserStore.getState().actions.setConnectionStatus('Live');
    };

    socket.onclose = () => {
        console.log('WebSocket disconnected');
        socket = null;
        useUserStore.getState().actions.setConnectionStatus('Отключено');
        // Попытка переподключения, если токен все еще есть
        setTimeout(() => {
            const currentToken = useUserStore.getState().jwtToken;
            if (currentToken) {
                connectWebSocket(currentToken);
            }
        }, reconnectInterval);
    };

    socket.onerror = (error) => {
        console.error('WebSocket error:', error);
        socket.close();
    };

    socket.onmessage = handleMessage;
};

export const disconnectWebSocket = () => {
    if (socket) {
        socket.close();
        socket = null;
    }
};