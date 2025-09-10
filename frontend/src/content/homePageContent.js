// frontend/src/content/homePageContent.js
import React from 'react';
import GroupAddIcon from '@mui/icons-material/GroupAdd';
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import SecurityIcon from '@mui/icons-material/Security';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import TimerIcon from '@mui/icons-material/Timer';
import HistoryIcon from '@mui/icons-material/History';
import FavoriteIcon from '@mui/icons-material/Favorite';
import PersonRemoveIcon from '@mui/icons-material/PersonRemove';
import BarChartIcon from '@mui/icons-material/BarChart';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import CakeIcon from '@mui/icons-material/Cake';

export const heroSection = {
    title: "Интеллектуальная автоматизация для ВКонтакте",
    subtitle: "Zenith — это ваш персональный SMM-ассистент, созданный для органического роста, повышения охватов и оптимизации вашего времени. Безопасно, эффективно, интеллектуально.",
    ctaButton: "Начать бесплатно"
};

export const featureList = [
    { icon: <PersonAddIcon />, title: "Добавление" },
    { icon: <GroupAddIcon />, title: "Прием заявок" },
    { icon: <ThumbUpIcon />, title: "Лайки в ленте" },
    { icon: <FavoriteIcon />, title: "Лайки друзьям" },
    { icon: <HistoryIcon />, title: "Просмотр историй" },
    { icon: <CakeIcon />, title: "Поздравления" },
    { icon: <PersonRemoveIcon />, title: "Чистка друзей" },
    { icon: <AccountTreeIcon />, title: "Сценарии" },
    { icon: <BarChartIcon />, title: "Аналитика" },
];

export const benefitsSection = {
    title: "Стратегическое преимущество для вашего профиля",
    subtitle: "Мы объединили передовые технологии и глубокое понимание алгоритмов социальных сетей, чтобы вы получали измеримый результат, не рискуя своим аккаунтом.",
    benefits: [
        {
            icon: <SecurityIcon />,
            title: "Безопасность — наш приоритет",
            description: "Система работает через временный токен доступа VK, не запрашивая ваш логин и пароль. Для максимальной анонимности реализована поддержка ваших личных прокси-серверов."
        },
        {
            icon: <AutoAwesomeIcon />,
            title: "Интеллектуальная имитация",
            description: "Наш алгоритм Humanizer™ подбирает динамические интервалы между действиями, делая автоматизацию неотличимой от ручной работы и минимизируя риски."
        },
        {
            icon: <TimerIcon />,
            title: "Автоматизация 24/7",
            description: "Создавайте сложные цепочки действий с помощью Сценариев. Настройте расписание один раз, и Zenith будет работать на вас круглосуточно, даже когда вы оффлайн."
        },
    ]
};

export const howItWorksSection = {
    title: "Всего 3 шага к результату",
    steps: [
        {
            number: "1",
            title: "Безопасная авторизация",
            description: "Получите временный ключ доступа VK. Мы никогда не запрашиваем и не храним ваш логин и пароль."
        },
        {
            number: "2",
            title: "Гибкая настройка",
            description: "Выберите действие, настройте мощные фильтры для точного таргетинга или создайте собственный сценарий работы по расписанию."
        },
        {
            number: "3",
            title: "Анализ и контроль",
            description: "Наблюдайте за выполнением каждой операции в реальном времени и отслеживайте рост вашего аккаунта с помощью наглядных графиков."
        }
    ]
};

export const algorithmsSection = {
    title: "Станьте приоритетом для алгоритмов VK",
    description: "Регулярная и естественная активность — ключ к увеличению охватов. Zenith помогает вашему профилю оставаться «живым» для алгоритмов, что привлекает внимание новой аудитории, повышает вовлеченность и стимулирует органический рост вашей популярности.",
};

export const ctaSection = {
    title: "Готовы начать?",
    subtitle: "Присоединяйтесь к Zenith сегодня и начните свой путь к эффективному продвижению.",
    ctaButton: "Попробовать бесплатно"
};