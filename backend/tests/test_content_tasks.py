# backend/tests/test_content_tasks.py

import pytest
import datetime
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path
from arq.connections import create_pool

from app.db.models import ScheduledPost, ScheduledPostStatus
from app.tasks.system_tasks import publish_scheduled_post_task
from app.arq_config import redis_settings
from tests.utils.task_runner import run_and_verify_task

TESTS_ROOT_DIR = Path(__file__).parent 

@pytest.fixture(scope="module", autouse=True)
def create_test_assets_folder():
    assets_dir = TESTS_ROOT_DIR / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "test_image_1.jpg").touch()
    (assets_dir / "test_image_2.jpg").touch()
    print(f"\n[PREP] Убедитесь, что в папке '{assets_dir.resolve()}' есть файлы 'test_image_1.jpg' и 'test_image_2.jpg'")

async def test_task_like_feed(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    user, headers = authorized_user_and_headers
    await run_and_verify_task(async_client, db_session, headers, "like_feed", {"count": 3, "filters": {}}, user.id)

async def test_task_view_stories(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    user, headers = authorized_user_and_headers
    await run_and_verify_task(async_client, db_session, headers, "view_stories", {}, user.id)


async def test_full_posting_cycle(
    async_client: AsyncClient,
    db_session: AsyncSession,
    authorized_user_and_headers: tuple
):
    """
    Тестирует полный цикл: загрузка, планирование 2 постов и их поочередная публикация.
    """
    user, headers = authorized_user_and_headers
    
    # === ШАГ 1: ЗАГРУЗКА ИЗОБРАЖЕНИЙ ===
    
    # 1.1. Загрузка двух локальных файлов
    print("\n[STEP 1.1] Пакетная загрузка двух локальных изображений...")
    image_paths = [TESTS_ROOT_DIR / "assets/test_image_1.jpg", TESTS_ROOT_DIR / "assets/test_image_2.jpg"]
    with open(image_paths[0], 'rb') as f1, open(image_paths[1], 'rb') as f2:
        files_to_upload = [
            ('images', (image_paths[0].name, f1, 'image/jpeg')),
            ('images', (image_paths[1].name, f2, 'image/jpeg'))
        ]
        upload_resp_local = await async_client.post("/api/v1/posts/upload-images-batch", headers=headers, files=files_to_upload)
    assert upload_resp_local.status_code == 200
    attachment_ids_local = upload_resp_local.json()["attachment_ids"]
    assert len(attachment_ids_local) == 2

    # 1.2. Загрузка изображения по URL
    pixiv_image_url = "https://i.pximg.net/img-master/img/2025/05/01/22/28/57/129918823_p0_master1200.jpg"
    print(f"[STEP 1.2] Загрузка изображения по URL: {pixiv_image_url}")
    upload_resp_url = await async_client.post("/api/v1/posts/upload-image-from-url", headers=headers, json={"image_url": pixiv_image_url})
    assert upload_resp_url.status_code == 200
    attachment_id_url = upload_resp_url.json()["attachment_id"]
    
    print("[STEP 1] Все изображения успешно загружены.")

    # === ШАГ 2: ПАКЕТНОЕ ПЛАНИРОВАНИЕ ===
    now = datetime.datetime.now(datetime.timezone.utc)
    timestamp_str = f"{now:%H:%M:%S}"
    
    # Пост 1 через 15 секунд
    publish_time_1 = now + datetime.timedelta(seconds=15)
    post_1_data = {
        "post_text": f"🤖 Пост №1 (2 локальных фото) в {timestamp_str}",
        "publish_at": publish_time_1.isoformat(),
        "attachments": attachment_ids_local
    }
    
    # Пост 2 через 45 секунд (30 секунд после первого)
    publish_time_2 = now + datetime.timedelta(seconds=45)
    post_2_data = {
        "post_text": f"🤖 Пост №2 (фото по URL) в {timestamp_str}",
        "publish_at": publish_time_2.isoformat(),
        "attachments": [attachment_id_url]
    }

    print(f"\n[STEP 2] Планирование двух постов:\n - Пост 1 на {publish_time_1}\n - Пост 2 на {publish_time_2}")
    resp = await async_client.post("/api/v1/posts/schedule-batch", headers=headers, json={"posts": [post_1_data, post_2_data]})
    assert resp.status_code == 201
    await db_session.commit() # Фиксируем, чтобы задача была видна
    post_ids = [p['id'] for p in resp.json()]
    assert len(post_ids) == 2
    print(f"[STEP 2] Посты (IDs: {post_ids}) успешно запланированы.")

    # === ШАГ 3: ИМИТАЦИЯ РАБОТЫ ВОРКЕРА ===
    print("\n[STEP 3] Имитация работы воркера...")
    arq_pool = await create_pool(redis_settings)
    worker_context = {'redis_pool': arq_pool}

    try:
        # Ожидание и запуск первой задачи
        await asyncio.sleep(16)
        print(f"[{datetime.datetime.now():%H:%M:%S}] Время для первого поста. Выполняем задачу для ID {post_ids[0]}...")
        await publish_scheduled_post_task(worker_context, post_id=post_ids[0], db_session_for_test=db_session)

        # Ожидание и запуск второй задачи
        await asyncio.sleep(30)
        print(f"[{datetime.datetime.now():%H:%M:%S}] Время для второго поста. Выполняем задачу для ID {post_ids[1]}...")
        await publish_scheduled_post_task(worker_context, post_id=post_ids[1], db_session_for_test=db_session)
    finally:
        await arq_pool.close()
    
    print("[STEP 3] Имитация завершена.")
    
    # === ШАГ 4: ПРОВЕРКА РЕЗУЛЬТАТОВ ===
    await db_session.commit() # Коммитим изменения после работы задач
    posts = (await db_session.execute(select(ScheduledPost).where(ScheduledPost.id.in_(post_ids)))).scalars().all()
    published_posts = [p for p in posts if p.status == ScheduledPostStatus.published]

    print("\n--- ФИНАЛЬНЫЕ РЕЗУЛЬТАТЫ ---")
    assert len(published_posts) == 2, f"Ожидалось 2 опубликованных поста, но опубликовано {len(published_posts)}."
    
    for post in posts:
        print(f"  - Пост ID {post.id}: Статус - {post.status.value}, VK ID - {post.vk_post_id or 'N/A'}")

    print("✓ Оба поста успешно опубликованы в соответствии с расписанием. Проверьте вашу страницу VK.")