// frontend/src/content/dashboardContent.js
import React from 'react';
import GroupAddIcon from '@mui/icons-material/GroupAdd';
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import RecommendIcon from '@mui/icons-material/Recommend';
import HistoryIcon from '@mui/icons-material/History';
import PersonRemoveIcon from '@mui/icons-material/PersonRemove';
import FavoriteIcon from '@mui/icons-material/Favorite';
import CakeIcon from '@mui/icons-material/Cake';

export const dashboardContent = {
    profile: {
        noStatus: "Статус не указан",
    },
    tasks: {
        launchButton: "Запустить",
        unknownError: "Произошла неизвестная ошибка.",
        unknownAction: "Неизвестное действие",
    },
    actionPanel: {
        title: "Панель действий",
        actions: [
            { key: 'accept_friends', icon: <GroupAddIcon />, title: 'Прием заявок' },
            { key: 'like_feed', icon: <ThumbUpIcon />, title: 'Лайки в ленте', countLabel: 'Количество лайков' },
            { key: 'add_recommended', icon: <RecommendIcon />, title: 'Добавить друзей', countLabel: 'Количество заявок' },
            { key: 'like_friends_feed', icon: <FavoriteIcon />, title: 'Лайки друзьям', countLabel: 'Количество лайков' },
            { key: 'view_stories', icon: <HistoryIcon />, title: 'Просмотр историй' },
            { key: 'remove_friends', icon: <PersonRemoveIcon />, title: 'Чистка друзей', countLabel: 'Максимум удалений' },
        ]
    },
    eventFeed: {
        title: "Лента событий",
        waiting: "Ожидание действий...",
        link: "[ссылка]"
    },
    activityChart: {
        title: "Статистика активности",
        periods: { day: "День", week: "Неделя", month: "Месяц" },
        series: { likes: "Лайки", requests: "Отправлено заявок", accepted: "Принято заявок" }
    },
    friendsAnalytics: {
        title: "Анализ друзей",
        total: "Всего",
        labels: ['Женщины', 'Мужчины', 'Не указан'],
        tooltipSuffix: "чел.",
        error: "Ошибка загрузки данных.",
        noData: "Нет друзей для анализа."
    },
    automations: {
        title: "Центр Автоматизации",
        list: [
            { key: 'like_feed', icon: <ThumbUpIcon />, title: 'Авто-лайки', description: 'Ежедневные лайки в ленте новостей.' },
            { key: 'add_recommended', icon: <RecommendIcon />, title: 'Авто-добавление', description: 'Ежедневные заявки в друзья.' },
            { key: 'birthday_congratulation', icon: <CakeIcon />, title: 'Авто-поздравления', description: 'Поздравления друзей с ДР.' },
        ]
    },
    modal: {
        titlePrefix: "Настройка",
        defaults: {
            count: 50,
            filters: { sex: 0, is_online: false, allow_closed_profiles: false, remove_banned: true, last_seen_hours: 0, last_seen_days: 0, min_friends: 0, min_followers: 0 },
            like_config: { enabled: false, targets: ['avatar'], count: 1 },
            send_message_on_add: false,
            message_text: "Привет! Увидел(а) тебя в рекомендациях, решил(а) добавиться. Будем знакомы!",
        },
        likeAfterRequest: {
            label: "Лайк после заявки",
            tooltip: "Автоматически ставить лайк на аватар или пост пользователя после отправки заявки. Работает только для открытых профилей.",
        },
        filters: {
            title: "Критерии и фильтры",
            onlineOnly: "Только онлайн",
            closedProfiles: { label: "Закрытые профили", tooltip: "Разрешить взаимодействие с пользователями, у которых закрыт профиль." },
            lastSeen: {
                label: "Был(а) в сети",
                options: [
                    { value: 0, label: "Неважно" }, { value: 1, label: "в течение часа" }, { value: 3, label: "в течение 3 часов" },
                    { value: 12, label: "в течение 12 часов" }, { value: 24, label: "в течение суток" }
                ]
            },
            sex: {
                label: "Пол",
                options: [{ value: 0, label: "Любой" }, { value: 1, label: "Женский" }, { value: 2, label: "Мужской" }]
            },
            removeBanned: { label: "Удаленные / забаненные", tooltip: "Удалить пользователей, чьи страницы были удалены или заблокированы." },
            inactive: {
                label: "Неактивные",
                options: [
                    { value: 0, label: "Не удалять" }, { value: 30, label: "Не заходил(а) > 1 мес." },
                    { value: 90, label: "Не заходил(а) > 3 мес." }, { value: 180, label: "Не заходил(а) > 6 мес." },
                    { value: 365, label: "Не заходил(а) > 1 года" }
                ]
            },
            friendsCount: {
                options: [ { value: 0, label: 'Любое' }, { value: 50, label: '> 50' }, { value: 100, label: '> 100' }, { value: 500, label: '> 500' } ]
            },
            followersCount: {
                options: [ { value: 0, label: 'Любое' }, { value: 100, label: '> 100' }, { value: 500, label: '> 500' }, { value: 1000, label: '> 1000' } ]
            },
        }
    }
};