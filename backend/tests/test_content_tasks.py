# backend/tests/test_content_tasks.py

import pytest
import datetime
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path

from app.db.models import User, ScheduledPost
from app.services.vk_api import VKAPI
from tests.utils.task_runner import run_and_verify_task, run_worker_for_duration

pytestmark = pytest.mark.asyncio

@pytest.fixture(scope="module", autouse=True)
def create_test_assets_folder():
    """Создает папку для тестовых изображений, если ее нет."""
    assets_dir = Path("backend/tests/assets")
    assets_dir.mkdir(exist_ok=True)
    # Вы можете добавить сюда код для скачивания тестовых картинок, если их нет
    # Например, с помощью requests или aiohttp
    print(f"\n[PREP] Убедитесь, что в папке '{assets_dir.resolve()}' есть файлы 'test_image_1.jpg' и 'test_image_2.jpg'")

async def test_task_like_feed(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    user, headers = authorized_user_and_headers
    payload = {"count": 3, "filters": {}}
    await run_and_verify_task(async_client, db_session, headers, "like_feed", payload, user.id)

async def test_task_view_stories(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    user, headers = authorized_user_and_headers
    await run_and_verify_task(async_client, db_session, headers, "view_stories", {}, user.id)

async def test_batch_upload_from_file(async_client: AsyncClient, authorized_user_and_headers: tuple):
    _, headers = authorized_user_and_headers
    print("\n--- Тестирование контента: ПАКЕТНАЯ ЗАГРУЗКА ФАЙЛОВ ---")
    
    image_paths = [Path("backend/tests/assets/test_image_1.jpg"), Path("backend/tests/assets/test_image_2.jpg")]
    for path in image_paths:
        if not path.exists():
            pytest.fail(f"Тестовое изображение не найдено: {path.resolve()}.")

    files_to_upload = [('images', (p.name, open(p, 'rb'), 'image/jpeg')) for p in image_paths]
    
    upload_resp = await async_client.post("/api/v1/posts/upload-images-batch", headers=headers, files=files_to_upload)
    
    for _, file_tuple in files_to_upload:
        file_tuple[1].close()

    assert upload_resp.status_code == 200, f"Ошибка при пакетной загрузке: {upload_resp.text}"
    attachment_ids = upload_resp.json().get("attachment_ids", [])
    
    assert len(attachment_ids) == len(image_paths), "Количество ID не совпадает с количеством файлов."
    print(f"✓ Пакетная загрузка {len(attachment_ids)} файлов прошла успешно.")


async def test_batch_schedule_posts(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple, vk_api_client: VKAPI):
    print("\n--- Тестирование контента: ПАКЕТНОЕ ПЛАНИРОВАНИЕ ПОСТОВ ---")
    user, headers = authorized_user_and_headers

    now = datetime.datetime.now(datetime.timezone.utc)
    posts_to_schedule = [
        {"post_text": f"🤖 Пакетный пост №1 (текст). Публикация через 30 сек. {int(now.timestamp())}", "publish_at": (now + datetime.timedelta(seconds=30)).isoformat()},
        {"image_url": "https://i.imgur.com/g2c3v4j.jpeg", "publish_at": (now + datetime.timedelta(seconds=60)).isoformat()}
    ]
    batch_payload = {"posts": posts_to_schedule}

    create_resp = await async_client.post("/api/v1/posts/schedule-batch", headers=headers, json=batch_payload)
    assert create_resp.status_code == 201, f"Ошибка при пакетном планировании: {create_resp.text}"
    created_posts_info = create_resp.json()
    post_ids = [p['id'] for p in created_posts_info]
    print(f"[ACTION] ✓ Успешно запланировано {len(post_ids)} постов. Они появятся на стене через 30 и 60 секунд.")

    await run_worker_for_duration(70)

    print("[VERIFY] Проверка статусов всех постов в базе данных...")
    db_session.expire_all()
    stmt = select(ScheduledPost).where(ScheduledPost.id.in_(post_ids))
    published_posts = (await db_session.execute(stmt)).scalars().all()
    
    assert len(published_posts) == len(post_ids)
    
    published_vk_ids = []
    for post in published_posts:
        assert post.status.value == "published", f"Пост ID={post.id} не опубликован! Статус: {post.status.value}"
        published_vk_ids.append(post.vk_post_id)
    
    print("✓ Все посты успешно опубликованы!")
    for i, vk_id in enumerate(published_vk_ids):
        print(f"  - Пост {i+1}: https://vk.com/wall{user.vk_id}_{vk_id}")

    print("[CLEANUP] Удаление созданных постов...")
    for vk_id in published_vk_ids:
        await vk_api_client._make_request("wall.delete", params={"post_id": vk_id})
        await asyncio.sleep(1)
    print("[CLEANUP] ✓ Тестовые посты удалены.")