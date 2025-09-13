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

// ИЗМЕНЕНИЕ: Единый источник правды для всех задач и автоматизаций
const tasks = {
    'like_feed': { 
        icon: <ThumbUpIcon />, 
        name: "Лайки в ленте новостей", 
        description: "Проставляет лайки на посты в ленте новостей.",
        modalTitle: "Лайки в ленте новостей", 
    },
    'add_recommended': { 
        icon: <RecommendIcon />, 
        name: "Добавление друзей", 
        description: "Отправляет заявки пользователям из списка рекомендаций.",
        modalTitle: "Добавление друзей из рекомендаций",
    },
     'accept_friends': { 
        icon: <GroupAddIcon />, 
        name: "Прием заявок в друзья",
        description: "Принимает входящие заявки в друзья по вашим фильтрам.",
        modalTitle: "Прием входящих заявок",
    },
    'remove_friends': { 
        icon: <PersonRemoveIcon />, 
        name: "Очистка списка друзей",
        description: "Удаляет неактивных и забаненных друзей.",
        modalTitle: "Чистка списка друзей",
    },
    'view_stories': { 
        icon: <HistoryIcon />, 
        name: "Просмотр историй",
        description: "Просматривает все доступные истории друзей.",
        modalTitle: "Просмотр историй",
    },
    'mass_messaging': { 
        icon: <SendIcon />, 
        name: "Массовая рассылка",
        description: "Отправляет сообщения друзьям по заданным критериям.",
        modalTitle: "Массовая отправка сообщений друзьям",
    },
    'leave_groups': { 
        icon: <GroupRemoveIcon />, 
        name: "Отписка от сообществ",
        description: "Отписывается от сообществ по ключевому слову.",
        modalTitle: 'Отписка от сообществ',
    },
    'join_groups': { 
        icon: <AddToPhotosIcon />, 
        name: "Вступление в группы",
        description: "Вступает в группы по ключевым словам.",
        modalTitle: 'Вступление в группы',
    },
    'birthday_congratulation': { 
        icon: <CakeIcon />, 
        name: "Поздравления с ДР", 
        description: "Поздравляет ваших друзей с Днем Рождения.",
    },
    'eternal_online': { 
        icon: <OnlinePredictionIcon />, 
        name: "Вечный онлайн", 
        description: "Поддерживает статус 'онлайн' для вашего аккаунта.",
    },
    'post_scheduler': {
        icon: <CalendarMonthIcon />,
        name: "Планировщик постов",
        description: "Создавайте и планируйте публикации наперед."
    }
};

export const content = {
    appName: "Zenith",
    nav: {
        dashboard: "Кабинет",
        scenarios: "Сценарии",
        posts: "Планировщик",
        team: "Команда",
        billing: "Тарифы",
        login: "Войти",
        logout: "Выйти",
    },
    tasks: tasks,
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