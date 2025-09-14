# frontend/Dockerfile -- ЗАЩИЩЕННАЯ ВЕРСИЯ

# --- Этап 1: Сборка зависимостей ---
FROM node:20-alpine AS deps
WORKDIR /app
# Копируем только файлы, необходимые для установки зависимостей
COPY package.json package-lock.json ./
# Устанавливаем зависимости в изолированном окружении
RUN npm ci

# --- Этап 2: Сборка исходного кода ---
FROM node:20-alpine AS builder
WORKDIR /app

# Сначала копируем исходный код. 
# На этом этапе .dockerignore ДОЛЖЕН предотвратить копирование локальных node_modules
COPY . .

# ТЕПЕРЬ ПРИНУДИТЕЛЬНО УДАЛЯЕМ ПАПКУ node_modules, если она вдруг скопировалась.
# Этот шаг гарантирует, что мы не используем локальные зависимости.
RUN rm -rf node_modules

# А теперь копируем "чистые" и "правильные" node_modules с первого этапа
COPY --from=deps /app/node_modules ./node_modules

# Переменная окружения для API
ARG REACT_APP_API_BASE_URL
ENV REACT_APP_API_BASE_URL=$REACT_APP_API_BASE_URL

# Запускаем сборку. Теперь react-scripts ОБЯЗАН быть на месте.
RUN npm run build

# --- Этап 3: Финальный образ для production ---
FROM nginx:1.27-alpine AS production

# Копируем собранные статические файлы
COPY --from=builder /app/dist /usr/share/nginx/html

# Открываем порт 80
EXPOSE 80

# Запускаем Nginx
CMD ["nginx", "-g", "daemon off;"]