import { toast } from 'react-hot-toast';
import { useStore } from '@/app/store';
import { queryClient } from './queryClient';

let socket = null;
let reconnectTimeout = null;

// УЛУЧШЕНИЕ: Внедряем стратегию Exponential Backoff для переподключения
let reconnectAttempts = 0;
const BASE_RECONNECT_INTERVAL = 3000; // Начинаем с 3 секунд
const MAX_RECONNECT_INTERVAL = 30000; // Максимальная задержка - 30 секунд

const getSocketUrl = () => {
  const apiUrl = import.meta.env.VITE_API_BASE_URL || window.location.origin;
  const wsUrl = new URL(apiUrl);
  wsUrl.protocol = wsUrl.protocol.replace('http', 'ws');
  wsUrl.pathname = '/api/v1/ws';
  return wsUrl.toString();
};

const scheduleReconnect = (token) => {
  if (reconnectTimeout) clearTimeout(reconnectTimeout);

  const delay = Math.min(
    MAX_RECONNECT_INTERVAL,
    BASE_RECONNECT_INTERVAL * Math.pow(2, reconnectAttempts)
  );

  console.log(
    `WebSocket: scheduling reconnect in ${delay / 1000}s (attempt ${reconnectAttempts + 1})`
  );

  reconnectTimeout = setTimeout(() => {
    reconnectAttempts++;
    connectWebSocket(token);
  }, delay);
};

const handleMessage = (event) => {
  try {
    const { type, payload } = JSON.parse(event.data);

    switch (type) {
      case 'log':
        // Можно добавить логику для отображения логов в UI, если потребуется
        console.log('WS Log:', payload);
        break;
      case 'stats_update':
        queryClient.invalidateQueries({ queryKey: ['userLimits'] });
        break;
      case 'task_history_update':
        // Этот метод более надежен, чем setQueryData, так как он просто помечает данные как "устаревшие",
        // а React Query сам решит, когда и как их обновить.
        queryClient.invalidateQueries({ queryKey: ['task_history'] });

        if (payload.status === 'SUCCESS' && payload.task_name) {
          toast.success(`Задача "${payload.task_name}" успешно завершена!`);
        }
        if (payload.status === 'FAILURE' && payload.task_name) {
          toast.error(
            `Задача "${payload.task_name}" провалена: ${payload.result}`,
            { duration: 8000 }
          );
        }
        break;

      case 'new_notification': {
        // ИСПРАВЛЕНИЕ: Добавлены фигурные скобки для создания блока
        queryClient.invalidateQueries({ queryKey: ['notifications'] });
        const message = payload.message;
        const options = { duration: 8000 };
        if (payload.level === 'error') toast.error(message, options);
        else if (payload.level === 'warning')
          toast.error(message, options); // toast.error для warning тоже хорошо, т.к. привлекает внимание
        else toast.success(message, { duration: 5000 });
        break;
      } // ИСПРАВЛЕНИЕ: Закрывающая скобка

      default:
        break;
    }
  } catch (error) {
    console.error('Error parsing WebSocket message:', error);
  }
};

export const connectWebSocket = (token) => {
  if (socket || !token) return;

  const url = `${getSocketUrl()}?token=${token}`;
  socket = new WebSocket(url);

  socket.onopen = () => {
    console.log('WebSocket connected');
    useStore.getState().actions.setConnectionStatus('На связи');
    reconnectAttempts = 0; // Сбрасываем счетчик при успешном подключении
    if (reconnectTimeout) clearTimeout(reconnectTimeout);
  };

  socket.onclose = (event) => {
    console.log(`WebSocket disconnected: ${event.code}`);
    socket = null;
    useStore.getState().actions.setConnectionStatus('Переподключение...');

    const currentToken = useStore.getState().token;
    if (currentToken) {
      scheduleReconnect(currentToken);
    }
  };

  socket.onerror = (error) => {
    console.error('WebSocket error:', error);
    if (socket) {
      socket.close();
    }
  };

  socket.onmessage = handleMessage;
};

export const disconnectWebSocket = () => {
  if (reconnectTimeout) clearTimeout(reconnectTimeout);
  reconnectAttempts = 0;
  if (socket) {
    socket.onclose = null;
    socket.close();
    socket = null;
    useStore.getState().actions.setConnectionStatus('Отключено');
  }
};
