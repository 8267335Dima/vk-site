# backend/app/core/exceptions.py

class BaseAppException(Exception):
    """Базовое исключение для приложения."""
    pass

class UserActionException(BaseAppException):
    """Базовое исключение для ошибок во время выполнения пользовательских задач."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

class UserLimitReachedError(UserActionException):
    """Вызывается, когда пользователь достигает дневного лимита."""
    pass

class InvalidActionSettingsError(UserActionException):
    """Вызывается, если настройки для действия некорректны."""
    pass

class AccountDeactivatedError(UserActionException):
    """Вызывается, если аккаунт пользователя ВКонтакте деактивирован."""
    pass