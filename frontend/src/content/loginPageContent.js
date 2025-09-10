export const loginPageContent = {
    title: "Вход в Social Pulse",
    subtitle: "Вставьте ключ доступа для входа",
    textFieldLabel: "Ссылка или ключ доступа VK",
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
};