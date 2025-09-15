# --- backend/app/api/endpoints/posts.py ---
import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from arq.connections import ArqRedis

# --- ИЗМЕНЕНИЯ ЗДЕСЬ ---
from app.db.session import get_db
from app.db.models import User, ScheduledPost
from app.api.dependencies import get_current_active_profile, get_arq_pool # Добавляем get_arq_pool
from app.api.schemas.posts import PostCreate, PostRead, PostUpdate, UploadedImageResponse
from app.services.vk_api import VKAPI
from app.core.security import decrypt_data
import structlog
# -------------------------

log = structlog.get_logger(__name__)
router = APIRouter()

@router.post("/upload-image", response_model=UploadedImageResponse)
async def upload_image_for_post(
    current_user: User = Depends(get_current_active_profile),
    image: UploadFile = File(...)
):
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    vk_api = VKAPI(access_token=vk_token)
    try:
        image_bytes = await image.read()
        attachment_id = await vk_api.upload_photo_for_wall(image_bytes)
        return UploadedImageResponse(attachment_id=attachment_id)
    except Exception as e:
        log.error("post.upload_image.failed", user_id=current_user.id, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось загрузить изображение.")

@router.post("", response_model=PostRead)
async def schedule_post(
    post_data: PostCreate,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
    # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
    arq_pool: ArqRedis = Depends(get_arq_pool)
    # -------------------------
):
    new_post = ScheduledPost(
        user_id=current_user.id,
        vk_profile_id=current_user.vk_id,
        **post_data.model_dump()
    )
    db.add(new_post)
    await db.flush() # Получаем ID для нового поста

    # --- ИЗМЕНЕНИЕ ЗДЕСЬ: Используем ARQ вместо Celery ---
    job = await arq_pool.enqueue_job(
        'publish_scheduled_post_task', # Имя задачи, зарегистрированной в worker.py
        post_id=new_post.id,
        _defer_by=post_data.publish_at - datetime.utcnow() # Откладываем задачу
    )
    # ----------------------------------------------------

    new_post.celery_task_id = job.job_id # Используем старое поле для хранения ID задачи ARQ
    await db.commit()
    await db.refresh(new_post)
    return new_post

# ... (Здесь могут быть ваши эндпоинты GET, PUT, DELETE для управления постами) ...