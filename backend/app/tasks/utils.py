# backend/app/tasks/utils.py
import asyncio

def run_async_from_sync(coro):
    """
    Надежно запускает асинхронную корутину из синхронной задачи Celery,
    используя стандартный asyncio.run().
    """
    return asyncio.run(coro)