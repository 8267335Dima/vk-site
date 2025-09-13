// --- frontend/src/content/content.js ---
import React from 'react';
import GroupAddIcon from '@mui/icons-material/GroupAdd';
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import RecommendIcon from '@mui/icons-material/Recommend';
import HistoryIcon from '@mui/icons-material/History';
import PersonRemoveIcon from '@mui/icons-material/PersonRemove';
import CakeIcon from '@mui/icons-material/Cake';
import SendIcon from '@mui/icons-material/Send';
import OnlinePredictionIcon from '@mui/icons-material/OnlinePrediction';
import GroupRemoveIcon from '@mui/icons-material/GroupRemove';
import AddToPhotosIcon from '@mui/icons-material/AddToPhotos';
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';

export const content = {
    appName: "Zenith",
    nav: {
        dashboard: "Кабинет",
        scenarios: "Сценарии",
        posts: "Планировщик",
        billing: "Тарифы",
        login: "Войти",
        logout: "Выйти",
    },
    actions: {
        'accept_friends': { icon: <GroupAddIcon />, title: 'Прием заявок', modalTitle: "Прием входящих заявок" },
        'like_feed': { icon: <ThumbUpIcon />, title: 'Лайкинг ленты', modalTitle: "Лайки в ленте новостей", modal_count_label: "Количество лайков" },
        'add_recommended': { icon: <RecommendIcon />, title: 'Добавление друзей', modalTitle: "Добавление друзей из рекомендаций", modal_count_label: "Количество заявок" },
        'view_stories': { icon: <HistoryIcon />, title: 'Просмотр историй', modalTitle: "Просмотр историй" },
        'remove_friends': { icon: <PersonRemoveIcon />, title: 'Чистка друзей', modalTitle: "Чистка списка друзей", modal_count_label: "Максимум удалений" },
        'mass_messaging': { icon: <SendIcon />, title: 'Отправка сообщений', modalTitle: "Массовая отправка сообщений друзьям", modal_count_label: "Количество сообщений" },
        'leave_groups': { icon: <GroupRemoveIcon />, title: 'Отписка от сообществ', modalTitle: 'Отписка от сообществ', modal_count_label: "Максимум отписок" },
        'join_groups': { icon: <AddToPhotosIcon />, title: 'Вступление в группы', modalTitle: 'Вступление в группы', modal_count_label: "Максимум вступлений" },
    },
    automations: [
        { id: "like_feed", icon: <ThumbUpIcon />, name: "Лайкинг ленты", description: "Проставляет лайки на посты в ленте новостей.", has_filters: true, group: 'standard' },
        { id: "add_recommended", icon: <RecommendIcon />, name: "Добавление друзей", description: "Отправляет заявки пользователям из списка рекомендаций.", has_filters: true, group: 'standard' },
        { id: "birthday_congratulation", icon: <CakeIcon />, name: "Поздравления с ДР", description: "Поздравляет ваших друзей с Днем Рождения.", has_filters: false, group: 'standard' },
        { id: "accept_friends", icon: <GroupAddIcon />, name: "Прием заявок", description: "Принимает входящие заявки в друзья по вашим фильтрам.", has_filters: true, group: 'standard' },
        { id: "remove_friends", icon: <PersonRemoveIcon />, name: "Чистка друзей", description: "Удаляет неактивных и забаненных друзей.", has_filters: true, group: 'standard' },
        { id: "leave_groups", icon: <GroupRemoveIcon />, name: "Отписка от сообществ", description: "Отписывается от сообществ по ключевому слову.", has_filters: true, group: 'standard' },
        { id: "join_groups", icon: <AddToPhotosIcon />, name: "Вступление в группы", description: "Вступает в группы по ключевым словам.", has_filters: true, group: 'standard' },
        { id: "view_stories", icon: <HistoryIcon />, name: "Просмотр историй", description: "Просматривает все доступные истории друзей.", has_filters: false, group: 'standard' },
        { id: "mass_messaging", icon: <SendIcon />, name: "Отправка сообщений", description: "Отправляет сообщения друзьям по заданным критериям.", has_filters: true, group: 'standard' },
        { id: "post_scheduler", icon: <CalendarMonthIcon />, name: "Планировщик постов", description: "Создавайте и планируйте публикации наперед.", has_filters: false, group: 'content' },
        { id: "eternal_online", icon: <OnlinePredictionIcon />, name: "Вечный онлайн", description: "Поддерживает статус 'онлайн' для вашего аккаунта.", has_filters: false, group: 'online' },
    ],
    loginPage: {
        title: "Добро пожаловать в Zenith",
        subtitle: "Ваш интеллектуальный ассистент для ВКонтакте",
        textFieldLabel: "Вставьте ключ доступа VK",
        buttonText: "Войти",
        tooltip: {
            step1: `1. Перейдите на сайт, нажав на <a href="https://vfeed.ru/v/token" target="_blank" rel="noopener noreferrer" style="color: #00BAE2; font-weight: 600;">эту ссылку</a>.`,
            step2: `2. Выберите "Windows Phone" или "Android" и разрешите доступ.`,
            step3: `3. Скопируйте ВСЮ ссылку из адресной строки браузера и вставьте в поле ниже.`
        },
        errors: {
            emptyToken: "Пожалуйста, вставьте ссылку или токен.",
            invalidUrl: "Некорректная ссылка. Скопируйте её полностью из адресной строки.",
            default: "Ошибка авторизации. Проверьте токен или убедитесь, что он не истек."
        }
    },
    modal: {
        launchButton: "Запустить",
        saveButton: "Сохранить",
        cancelButton: "Отмена",
        filtersTitle: "Критерии и фильтры",
        likeAfterRequest: {
            label: "Лайк после заявки",
            tooltip: "Автоматически ставить лайк на аватар пользователя после отправки заявки. Работает только для открытых профилей.",
        },
        messageOnAdd: {
            label: "Сообщение при добавлении",
            tooltip: "Отправить приветственное сообщение вместе с заявкой в друзья.",
            helperText: "Используйте {name} для подстановки имени."
        },
        massMessage: {
            onlyNewDialogsLabel: "Только новые диалоги",
            tooltip: "Отправить сообщение только тем друзьям, с которыми у вас еще нет начатой переписки."
        }
    }
};
