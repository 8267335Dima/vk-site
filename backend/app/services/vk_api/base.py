import aiohttp
import asyncio

# --- ИСКЛЮЧЕНИЯ ---
class VKAPIError(Exception):
    def __init__(self, message: str, error_code: int):
        self.message = message
        self.error_code = error_code
        super().__init__(f"VK API Error [{self.error_code}]: {self.message}")

class VKAuthError(VKAPIError): pass
class VKRateLimitError(VKAPIError): pass
class VKAccessDeniedError(VKAPIError): pass
class VKFloodControlError(VKAPIError): pass
class VKCaptchaError(VKAPIError): pass
class VKTooManyRequestsError(VKAPIError): pass

ERROR_CODE_MAP = {
    5: VKAuthError, 6: VKRateLimitError, 9: VKFloodControlError, 14: VKCaptchaError,
    15: VKAccessDeniedError, 18: VKAccessDeniedError, 29: VKTooManyRequestsError,
    203: VKAccessDeniedError, 902: VKAccessDeniedError,
}

# --- БАЗОВЫЙ КЛАСС ДЛЯ РАЗДЕЛОВ ---
class BaseVKSection:
    def __init__(self, request_method: callable):
        self._make_request = request_method