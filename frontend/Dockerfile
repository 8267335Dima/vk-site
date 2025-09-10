# frontend/Dockerfile

# --- STAGE 1: Build ---
FROM node:20-alpine AS builder
WORKDIR /app

# Копируем package.json и yarn.lock для кеширования установки зависимостей
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

# Теперь копируем остальной код приложения
COPY . .

# Передаем переменную сборки из docker-compose.yml
ARG REACT_APP_API_BASE_URL
ENV REACT_APP_API_BASE_URL=$REACT_APP_API_BASE_URL

# Собираем production-билд
RUN yarn build


# --- STAGE 2: Serve ---
FROM nginx:1.23-alpine

# Копируем готовый билд из предыдущей стадии
COPY --from=builder /app/build /usr/share/nginx/html

# Копируем конфиг Nginx для правильной работы React Router
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Открываем порт 80, на котором работает Nginx
EXPOSE 80

# Запускаем Nginx
CMD ["nginx", "-g", "daemon off;"]
