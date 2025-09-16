# --- backend/app/api/endpoints/posts.py ---
import datetime
import asyncio
import aiohttp
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Body
from sqlalchemy.ext.asyncio import AsyncSession
# --- ИЗМЕНЕНИЕ: Добавляем импорт AsyncGenerator ---
from typing import List, Optional, AsyncGenerator
# -----------------------------------------------
from arq.connections import ArqRedis

from app.db.session import get_db
from app.db.models import User, ScheduledPost
from app.api.dependencies import get_current_active_profile, get_arq_pool
from app.api.schemas.posts import PostCreate, PostRead, UploadedImagesResponse, PostBatchCreate, UploadedImageResponse
from app.services.vk_api import VKAPI
from app.core.security import decrypt_data
from app.repositories.stats import StatsRepository
import structlog

log = structlog.get_logger(__name__)
router = APIRouter()

# --- ИЗМЕНЕНИЕ: Корректная аннотация типа для асинхронного генератора ---
async def get_vk_api(current_user: User = Depends(get_current_active_profile)) -> AsyncGenerator[VKAPI, None]:
# ----------------------------------------------------------------------
    """Зависимость для получения готового VK API клиента."""
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    if not vk_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалидный токен VK.")
    
    vk_api_client = VKAPI(access_token=vk_token)
    try:
        yield vk_api_client
    finally:
        await vk_api_client.close()

@router.post("/upload-image-file", response_model=UploadedImageResponse, summary="Загрузить изображение с диска")
async def upload_image_file(
    vk_api: VKAPI = Depends(get_vk_api),
    image: UploadFile = File(...)
):
    """Принимает файл, загружает в VK и возвращает attachment_id."""
    try:
        image_bytes = await image.read()
        # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
        attachment_id = await vk_api.photos.upload_for_wall(image_bytes)
        return UploadedImageResponse(attachment_id=attachment_id)
    except Exception as e:
        log.error("post.upload_image_file.failed", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось загрузить изображение.")

async def _download_image_from_url(url: str) -> bytes:
    """Скачивает изображение по URL и возвращает его в виде байтов."""
    if not any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL должен вести на изображение (jpg, png, gif).")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as response:
                response.raise_for_status()
                return await response.read()
    except aiohttp.ClientError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Не удалось скачать изображение по URL: {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Внутренняя ошибка при скачивании изображения: {e}")

@router.post("/upload-images-batch", response_model=UploadedImagesResponse, summary="Загрузить несколько изображений с диска")
async def upload_images_batch(
    vk_api: VKAPI = Depends(get_vk_api),
    images: List[UploadFile] = File(...)
):
    """Принимает список файлов, параллельно загружает их в VK и возвращает список attachment_id."""
    if len(images) > 10:
        raise HTTPException(status_code=400, detail="Можно загрузить не более 10 изображений за раз.")

    async def upload_one(image: UploadFile):
        try:
            image_bytes = await image.read()
            # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
            return await vk_api.photos.upload_for_wall(image_bytes)
        except Exception as e:
            log.error("batch_upload.single_file_error", filename=image.filename, error=str(e))
            return None

    tasks = [upload_one(img) for img in images]
    results = await asyncio.gather(*tasks)
    
    successful_attachments = [res for res in results if res is not None]
    
    if not successful_attachments:
        raise HTTPException(status_code=500, detail="Не удалось загрузить ни одно из изображений.")
        
    return UploadedImagesResponse(attachment_ids=successful_attachments)

@router.post("/schedule-batch", response_model=List[PostRead], status_code=status.HTTP_201_CREATED, summary="Запланировать несколько постов")
async def schedule_batch_posts(
    batch_data: PostBatchCreate,
    current_user: User = Depends(get_current_active_profile),
    vk_api: VKAPI = Depends(get_vk_api),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool)
):
    """Принимает список постов и планирует их все одним запросом, проверяя лимиты."""
    created_posts_db = []
    
    stats_repo = StatsRepository(db)
    today_stats = await stats_repo.get_or_create_today_stats(current_user.id)
    
    posts_to_create_count = len(batch_data.posts)
    if posts_to_create_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Список постов для планирования не может быть пустым.")

    if today_stats.posts_created_count + posts_to_create_count > current_user.daily_posts_limit:
        remaining = current_user.daily_posts_limit - today_stats.posts_created_count
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Достигнут дневной лимит на создание постов. Осталось: {remaining if remaining > 0 else 0}"
        )
    
    for post_data in batch_data.posts:
        final_attachments = post_data.attachments or []
        if post_data.image_url:
            try:
                image_bytes = await _download_image_from_url(str(post_data.image_url))
                # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
                attachment_id = await vk_api.photos.upload_for_wall(image_bytes)
                final_attachments.append(attachment_id)
            except HTTPException as e:
                log.warn("schedule_batch.image_download_failed", url=post_data.image_url, detail=e.detail)
                continue

        new_post = ScheduledPost(
            user_id=current_user.id,
            vk_profile_id=current_user.vk_id,
            post_text=post_data.post_text,
            attachments=final_attachments,
            publish_at=post_data.publish_at
        )
        db.add(new_post)
        created_posts_db.append(new_post)

    if not created_posts_db:
        raise HTTPException(status_code=400, detail="Не удалось создать ни одного поста из пакета (возможно, из-за ошибок загрузки изображений).")

    today_stats.posts_created_count += len(created_posts_db)
    
    await db.flush()

    for post in created_posts_db:
        job = await arq_pool.enqueue_job(
            'publish_scheduled_post_task',
            post_id=post.id,
            _defer_until=post.publish_at
        )
        post.celery_task_id = job.job_id

    await db.commit()
    
    for post in created_posts_db:
        await db.refresh(post)

    return created_posts_db