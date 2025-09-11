// frontend/src/content/content.js
import React from 'react';
import GroupAddIcon from '@mui/icons-material/GroupAdd';
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import RecommendIcon from '@mui/icons-material/Recommend';
import HistoryIcon from '@mui/icons-material/History';
import PersonRemoveIcon from '@mui/icons-material/PersonRemove';
import FavoriteIcon from '@mui/icons-material/Favorite';
import CakeIcon from '@mui/icons-material/Cake';
import SendIcon from '@mui/icons-material/Send';
import OnlinePredictionIcon from '@mui/icons-material/OnlinePrediction';

export const content = {
    appName: "Zenith",
    nav: {
        dashboard: "Кабинет",
        scenarios: "Сценарии",
        billing: "Тарифы",
        login: "Войти",
        logout: "Выйти",
    },
    actions: { // Для ActionPanel и модальных окон
        'accept_friends': { icon: <GroupAddIcon />, title: 'Прием заявок', modalTitle: "Прием входящих заявок" },
        'like_feed': { icon: <ThumbUpIcon />, title: 'Лайки в ленте', modalTitle: "Лайки в ленте новостей" },
        'add_recommended': { icon: <RecommendIcon />, title: 'Добавить друзей', modalTitle: "Добавление друзей из рекомендаций" },
        'like_friends_feed': { icon: <FavoriteIcon />, title: 'Лайки друзьям', modalTitle: "Лайки на посты друзей" },
        'view_stories': { icon: <HistoryIcon />, title: 'Просмотр историй', modalTitle: "Просмотр историй" },
        'remove_friends': { icon: <PersonRemoveIcon />, title: 'Чистка друзей', modalTitle: "Чистка списка друзей" },
        'mass_messaging': { icon: <SendIcon />, title: 'Массовая рассылка', modalTitle: "Массовая рассылка друзьям" },
    },
    automations: { // Для AutomationsWidget
        'like_feed': { icon: <ThumbUpIcon />, title: 'Авто-лайки в ленте' },
        'add_recommended': { icon: <RecommendIcon />, title: 'Авто-добавление друзей' },
        'birthday_congratulation': { icon: <CakeIcon />, title: 'Авто-поздравления' },
        'accept_friends': { icon: <GroupAddIcon />, title: 'Авто-прием заявок' },
        'remove_friends': { icon: <PersonRemoveIcon />, title: 'Авто-чистка друзей' },
        'view_stories': { icon: <HistoryIcon />, title: 'Авто-просмотр историй' },
        'like_friends_feed': { icon: <FavoriteIcon />, title: 'Авто-лайки друзьям' },
        'mass_messaging': { icon: <SendIcon />, title: 'Авто-рассылка' },
        'eternal_online': { icon: <OnlinePredictionIcon />, title: 'Вечный онлайн' },
    },
    loginPage: {
        title: "Добро пожаловать в Zenith",
        subtitle: "Ваш интеллектуальный ассистент для ВКонтакте",
        textFieldLabel: "Вставьте ключ доступа VK",
        buttonText: "Войти",
        tooltip: {
            step1: `1. Перейдите на сайт <a href="https://vkhost.github.io/" target="_blank" rel="noopener noreferrer">vkhost.github.io</a>.`,
            step2: `2. Нажмите "Kate Mobile" и разрешите доступ.`,
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


