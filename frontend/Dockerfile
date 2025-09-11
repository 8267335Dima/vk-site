# frontend/Dockerfile

# --- Этап 1: Сборка зависимостей ---
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json ./
COPY package-lock.json ./
RUN npm ci

# --- Этап 2: Сборка исходного кода ---
FROM deps AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Переменная окружения для API
ARG REACT_APP_API_BASE_URL
ENV REACT_APP_API_BASE_URL=$REACT_APP_API_BASE_URL
RUN npm run build

# --- Этап 3: Финальный образ с Nginx для Production ---
FROM nginx:1.27-alpine AS production
# Копируем кастомный конфиг Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Копируем собранные статические файлы
COPY --from=builder /app/build /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

# --- Этап для разработки (не используется в прод-сборке) ---
FROM deps AS development
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
EXPOSE 3000
CMD ["npm", "start"]