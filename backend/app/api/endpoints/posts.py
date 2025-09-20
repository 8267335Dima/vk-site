# --- backend/app/api/endpoints/posts.py ---
import datetime
import asyncio
import aiohttp
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, AsyncGenerator
from arq.connections import ArqRedis

from app.db.session import get_db
from app.db.models import User, ScheduledPost
from app.api.dependencies import get_current_active_profile, get_arq_pool
# --- ИЗМЕНЕНИЕ: Добавляем новую схему ---
from sqlalchemy import select # --- ДОБАВЛЕНО ---
from app.db.models import User, ScheduledPost, Group # --- ДОБАВЛЕНО Group ---
from app.api.schemas.posts import (
    PostCreate, PostRead, UploadedImagesResponse, PostBatchCreate, 
    UploadedImageResponse, UploadImageFromUrlRequest, UploadImagesFromUrlsRequest,
    PostUpdateSchedule # --- НОВАЯ СХЕМА ---
)
from app.services.vk_api import VKAPI
from app.core.security import decrypt_data
from app.repositories.stats import StatsRepository
import structlog

log = structlog.get_logger(__name__)
router = APIRouter()

async def get_vk_api(current_user: User = Depends(get_current_active_profile)) -> AsyncGenerator[VKAPI, None]:
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    if not vk_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалидный токен VK.")
    
    vk_api_client = VKAPI(access_token=vk_token)
    try:
        yield vk_api_client
    finally:
        await vk_api_client.close()

async def _download_image_from_url(url: str) -> bytes:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://www.pixiv.net/"
    }
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=20) as response:
                response.raise_for_status()
                return await response.read()
    except aiohttp.ClientError as e:
        log.error("image_download.failed", url=url, status_code=getattr(e, 'status', None), message=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Не удалось скачать изображение по URL: {e}")
    except Exception as e:
        log.error("image_download.unknown_error", url=url, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Внутренняя ошибка при скачивании изображения: {e}")

# --- НОВЫЙ ЭНДПОИНТ ДЛЯ ПАКЕТНОЙ ЗАГРУЗКИ ПО URL ---
@router.post("/upload-images-from-urls-batch", response_model=UploadedImagesResponse, summary="Загрузить несколько изображений по URL")
async def upload_images_from_urls_batch(
    request_data: UploadImagesFromUrlsRequest,
    vk_api: VKAPI = Depends(get_vk_api)
):
    """Принимает список URL, параллельно скачивает и загружает их в VK."""

    async def upload_one_url(url: str):
        try:
            image_bytes = await _download_image_from_url(url)
            return await vk_api.photos.upload_for_wall(image_bytes)
        except Exception as e:
            log.warn("batch_url_upload.single_url_error", url=url, error=str(e))
            return None

    tasks = [upload_one_url(str(url)) for url in request_data.image_urls]
    results = await asyncio.gather(*tasks)
    
    successful_attachments = [res for res in results if res is not None]
    
    if not successful_attachments:
        raise HTTPException(status_code=500, detail="Не удалось загрузить ни одно из изображений по указанным URL.")
        
    return UploadedImagesResponse(attachment_ids=successful_attachments)
# --- КОНЕЦ НОВОГО ЭНДПОИНТА ---

@router.post("/upload-image-from-url", response_model=UploadedImageResponse, summary="Загрузить изображение по URL")
async def upload_image_from_url(
    request_data: UploadImageFromUrlRequest,
    vk_api: VKAPI = Depends(get_vk_api)
):
    try:
        image_bytes = await _download_image_from_url(str(request_data.image_url))
        attachment_id = await vk_api.photos.upload_for_wall(image_bytes)
        return UploadedImageResponse(attachment_id=attachment_id)
    except aiohttp.ClientError as e:
        log.error("image_download.client_error", url=request_data.image_url, error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Не удалось скачать изображение по URL: {e}")
    except HTTPException as e:
        raise e
    except Exception as e:
        log.error("post.upload_image_url.failed", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось обработать и загрузить изображение.")


@router.post("/upload-image-file", response_model=UploadedImageResponse, summary="Загрузить изображение с диска")
async def upload_image_file(
    vk_api: VKAPI = Depends(get_vk_api),
    image: UploadFile = File(...)
):
    try:
        image_bytes = await image.read()
        attachment_id = await vk_api.photos.upload_for_wall(image_bytes)
        return UploadedImageResponse(attachment_id=attachment_id)
    except Exception as e:
        log.error("post.upload_image_file.failed", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось загрузить изображение.")


@router.post("/upload-images-batch", response_model=UploadedImagesResponse, summary="Загрузить несколько изображений с диска")
async def upload_images_batch(
    vk_api: VKAPI = Depends(get_vk_api),
    images: List[UploadFile] = File(...)
):
    if len(images) > 10:
        raise HTTPException(status_code=400, detail="Можно загрузить не более 10 изображений за раз.")

    async def upload_one(image: UploadFile):
        try:
            image_bytes = await image.read()
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
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool)
):
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
        new_post = ScheduledPost(
            user_id=current_user.id,
            vk_profile_id=current_user.vk_id,
            post_text=post_data.post_text,
            attachments=post_data.attachments or [],
            publish_at=post_data.publish_at
        )
        db.add(new_post)
        created_posts_db.append(new_post)

    if not created_posts_db:
        raise HTTPException(status_code=400, detail="Не удалось создать ни одного поста из пакета.")

    today_stats.posts_created_count += len(created_posts_db)
    
    await db.flush()

    for post in created_posts_db:
        job = await arq_pool.enqueue_job(
            'publish_scheduled_post_task',
            post_id=post.id,
            _defer_until=post.publish_at
        )
        post.arq_job_id = job.job_id

    await db.commit()
    
    for post in created_posts_db:
        await db.refresh(post)

    return created_posts_db

@router.get("/schedule/calendar", response_model=List[PostRead])
async def get_posts_for_calendar(
    start_date: datetime.date,
    end_date: datetime.date,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    """
    Возвращает все запланированные и опубликованные посты пользователя
    в указанном диапазоне дат для отображения в календаре.
    """
    if (end_date - start_date).days > 90:
        raise HTTPException(status_code=400, detail="Диапазон дат не может превышать 90 дней.")
        
    stmt = select(ScheduledPost).where(
        ScheduledPost.user_id == current_user.id,
        ScheduledPost.publish_at.between(
            datetime.datetime.combine(start_date, datetime.time.min),
            datetime.datetime.combine(end_date, datetime.time.max)
        )
    ).order_by(ScheduledPost.publish_at)
    
    result = await db.execute(stmt)
    return result.scalars().all()

# --- НОВЫЙ ЭНДПОИНТ ДЛЯ ОБНОВЛЕНИЯ ДАТЫ (DRAG-AND-DROP) ---
@router.patch("/schedule/{post_id}/reschedule", response_model=PostRead)
async def reschedule_post(
    post_id: int,
    schedule_data: PostUpdateSchedule,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool)
):
    """
    Изменяет время публикации запланированного поста.
    """
    post = await db.get(ScheduledPost, post_id)
    if not post or post.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Пост не найден.")
    if post.status != "scheduled":
        raise HTTPException(status_code=400, detail="Можно перенести только запланированный пост.")

    # Отменяем старую ARQ задачу
    if post.arq_job_id:
        try:
            await arq_pool.abort_job(post.arq_job_id)
        except: # Игнорируем ошибки, если задача уже выполнилась или не найдена
            pass
            
    # Обновляем пост
    post.publish_at = schedule_data.publish_at
    
    # Создаем новую ARQ задачу
    job = await arq_pool.enqueue_job(
        'publish_scheduled_post_task',
        post_id=post.id,
        _defer_until=post.publish_at
    )
    post.arq_job_id = job.job_id
    
    await db.commit()
    await db.refresh(post)
    
    return post