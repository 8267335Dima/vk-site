# backend/app/services/proxy_service.py
import aiohttp
import asyncio
from typing import Tuple

class ProxyService:
    @staticmethod
    async def check_proxy(proxy_url: str) -> Tuple[bool, str]:
        if not proxy_url:
            return False, "URL прокси не может быть пустым."

        test_url = "https://api.vk.com/method/utils.getServerTime"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(test_url, proxy=proxy_url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "response" in data:
                            return True, "Прокси успешно работает."
                    
                    return False, f"Сервер ответил с кодом: {response.status}"

        except aiohttp.ClientProxyConnectionError as e:
            return False, f"Ошибка подключения к прокси: {e}"
        except aiohttp.ClientError as e:
            return False, f"Сетевая ошибка: {e}"
        except asyncio.TimeoutError:
            return False, "Тайм-аут подключения (10 секунд)."
        except Exception as e:
            return False, f"Неизвестная ошибка: {e}"