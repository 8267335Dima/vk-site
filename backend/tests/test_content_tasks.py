# backend/tests/test_content_tasks.py

import pytest
import datetime
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path

# Убедитесь, что все эти импорты есть в начале файла
from app.db.models import ScheduledPost, ScheduledPostStatus
from app.services.vk_api import VKAPI
from tests.utils.task_runner import run_and_verify_task, run_worker_for_duration

# Определяем путь к директории тестов
TESTS_ROOT_DIR = Path(__file__).parent 

@pytest.fixture(scope="module", autouse=True)
def create_test_assets_folder():
    assets_dir = TESTS_ROOT_DIR / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n[PREP] Убедитесь, что в папке '{assets_dir.resolve()}' есть файлы 'test_image_1.jpg' и 'test_image_2.jpg'")


async def test_task_like_feed(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    user, headers = authorized_user_and_headers
    await run_and_verify_task(async_client, db_session, headers, "like_feed", {"count": 3, "filters": {}}, user.id)


async def test_task_view_stories(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    user, headers = authorized_user_and_headers
    await run_and_verify_task(async_client, db_session, headers, "view_stories", {}, user.id)


async def test_batch_upload_from_file(async_client: AsyncClient, authorized_user_and_headers: tuple):
    _, headers = authorized_user_and_headers
    image_paths = [TESTS_ROOT_DIR / "assets/test_image_1.jpg", TESTS_ROOT_DIR / "assets/test_image_2.jpg"]
    
    # Используем with для корректного закрытия файлов
    with open(image_paths[0], 'rb') as f1, open(image_paths[1], 'rb') as f2:
        files_to_upload = [
            ('images', (image_paths[0].name, f1, 'image/jpeg')),
            ('images', (image_paths[1].name, f2, 'image/jpeg'))
        ]
        upload_resp = await async_client.post("/api/v1/posts/upload-images-batch", headers=headers, files=files_to_upload)
    
    assert upload_resp.status_code == 200
    assert len(upload_resp.json().get("attachment_ids", [])) == 2


async def test_batch_schedule_and_publish(
    async_client: AsyncClient,
    db_session: AsyncSession,
    authorized_user_and_headers: tuple,
    vk_api_client: VKAPI
):
    user, headers = authorized_user_and_headers
    
    # --- ШАГ 1: Загружаем локальный файл для первого поста ---
    print("\n[STEP 1] Загрузка локального изображения для первого поста...")
    image_path = TESTS_ROOT_DIR / "assets/test_image_1.jpg"
    assert image_path.exists(), "Тестовое изображение test_image_1.jpg не найдено!"

    with open(image_path, "rb") as f:
        files_to_upload = {'image': (image_path.name, f, 'image/jpeg')}
        upload_resp = await async_client.post("/api/v1/posts/upload-image-file", headers=headers, files=files_to_upload)
    
    assert upload_resp.status_code == 200
    attachment_id_local = upload_resp.json().get("attachment_id")
    assert attachment_id_local
    print(f"[STEP 1] Локальное изображение успешно загружено, attachment_id: {attachment_id_local}")

    # --- ШАГ 2: Планируем два поста с реальным временным интервалом ---
    now = datetime.datetime.now(datetime.timezone.utc)
    timestamp_str = f"{now:%H:%M:%S}"

    # Пост №1 (с локальным файлом) через 20 секунд
    publish_time_1 = now + datetime.timedelta(seconds=20)
    post_1_data = {
        "post_text": f"🤖 Локальный пост в {timestamp_str}", 
        "publish_at": publish_time_1.isoformat(),
        "attachments": [attachment_id_local]
    }

    # Пост №2 (с загрузкой по URL) через 40 секунд
    publish_time_2 = now + datetime.timedelta(seconds=40)
    post_2_data = {
        "post_text": f"🤖 URL пост в {timestamp_str}", 
        "publish_at": publish_time_2.isoformat(),
        "image_url": "https://i.imgur.com/gT762v2.jpeg" # Надежный URL для теста
    }

    print(f"\n[STEP 2] Планирование двух постов:")
    print(f" - Пост 1 на {publish_time_1.isoformat()}")
    print(f" - Пост 2 на {publish_time_2.isoformat()}")

    resp = await async_client.post("/api/v1/posts/schedule-batch", headers=headers, json={"posts": [post_1_data, post_2_data]})
    assert resp.status_code == 201, f"Ошибка при планировании постов: {resp.text}"
    
    # Фиксируем транзакцию, чтобы воркер увидел задачи
    await db_session.commit()
    post_ids = [p['id'] for p in resp.json()]
    print(f"[STEP 2] Посты (IDs: {post_ids}) успешно запланированы.")

    # --- ШАГ 3: Запускаем воркер и ждем достаточно времени для публикации обоих постов ---
    wait_duration = 50 # секунд
    print(f"\n[STEP 3] Запускаем воркер и ждем {wait_duration} секунд...")
    await run_worker_for_duration(wait_duration)
    
    # --- ШАГ 4: Проверяем результат ---
    posts = (await db_session.execute(select(ScheduledPost).where(ScheduledPost.id.in_(post_ids)))).scalars().all()
    
    published_posts = [p for p in posts if p.status == ScheduledPostStatus.published]
    failed_posts = [p for p in posts if p.status == ScheduledPostStatus.failed]

    print("\n--- РЕЗУЛЬТАТЫ ПУБЛИКАЦИИ ---")
    print(f"Опубликовано: {len(published_posts)}")
    print(f"Ошибок: {len(failed_posts)}")
    for p in failed_posts:
        print(f"  - Пост ID {p.id} провалился с ошибкой: {p.error_message}")
    
    assert len(published_posts) == 2, "Ожидалось, что оба поста будут опубликованы успешно."
    print("✓ Оба поста успешно опубликованы в VK. Проверьте свою страницу.")

    # --- ШАГ 5: Очистка (отключено по вашему запросу) ---
    # print("\nОчистка постов из VK отключена.")
    # for post in published_posts:
    #     if post.vk_post_id:
    #         print(f"Очистка: удаляем пост {post.vk_post_id} из VK...")
    #         await vk_api_client.wall.delete(post_id=int(post.vk_post_id), owner_id=user.vk_id)
    #         await asyncio.sleep(1)