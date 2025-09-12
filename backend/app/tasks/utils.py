# backend/app/tasks/utils.py
import asyncio

def run_async_from_sync(coro):
    """
    Надежно запускает корутину из синхронного кода, используя существующий 
    или новый event loop. Корректно работает в окружении, где цикл событий
    уже может быть запущен (например, Celery с gevent).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # 'RuntimeError: There is no running event loop'
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        # Если цикл уже запущен, безопасно выполняем корутину в нем
        # и дожидаемся результата.
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()
    else:
        # Если цикла нет, запускаем его для выполнения нашей задачи.
        return loop.run_until_complete(coro)