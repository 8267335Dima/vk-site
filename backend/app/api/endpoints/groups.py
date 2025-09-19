# backend/app/api/endpoints/groups.py
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.services.vk_api import VKAPI
from app.core.security import decrypt_data
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional
from app.db.session import get_db
from app.db.models import User, Group
from app.api.dependencies import get_current_active_profile
from app.api.schemas.groups import AddGroupRequest, AvailableGroupsResponse, GroupRead
from app.services.group_identity_service import GroupIdentityService
from app.core.security import encrypt_data
from app.services.vk_api.base import VKAPIError
from app.api.schemas.posts import UploadedImagesResponse, UploadedImageResponse # Переиспользуем схемы
from app.api.endpoints.posts import _download_image_from_url # Переиспользуем хелпер
from app.repositories.stats import StatsRepository

router = APIRouter()

@router.post("", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
async def add_managed_group(
    request_data: AddGroupRequest,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    """Добавляет сообщество в список управляемых."""
    group_info = await GroupIdentityService.get_group_info_by_token(
        request_data.access_token, request_data.vk_group_id
    )
    if not group_info:
        raise HTTPException(status_code=400, detail="Неверный токен доступа или ID сообщества.")

    existing = (await db.execute(select(Group).where(Group.vk_group_id == request_data.vk_group_id))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Это сообщество уже добавлено в систему.")

    new_group = Group(
        **group_info,
        admin_user_id=current_user.id,
        encrypted_access_token=encrypt_data(request_data.access_token)
    )
    db.add(new_group)
    await db.commit()
    await db.refresh(new_group)
    
    return new_group

@router.get("", response_model=AvailableGroupsResponse)
async def get_managed_groups(
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    """Возвращает список управляемых сообществ."""
    await db.refresh(current_user, ['managed_groups'])
    return {"groups": current_user.managed_groups}

class GroupPostCreate(BaseModel):
    message: str = Field("", max_length=4000)
    attachments: Optional[List[str]] = Field(default_factory=list, max_length=10)


@router.post("/{group_id}/wall", status_code=status.HTTP_201_CREATED)
async def post_to_group_wall(
    group_id: int,
    post_data: GroupPostCreate,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    """Публикует новый пост на стене управляемого сообщества с проверкой лимитов."""

    # <<< ДОБАВЛЕНО: Блок проверки лимитов >>>
    stats_repo = StatsRepository(db)
    today_stats = await stats_repo.get_or_create_today_stats(current_user.id)

    if today_stats.posts_created_count >= current_user.daily_posts_limit:
        remaining = current_user.daily_posts_limit - today_stats.posts_created_count
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Достигнут дневной лимит на создание постов. Осталось: {remaining if remaining > 0 else 0}"
        )
    # <<< КОНЕЦ БЛОКА ПРОВЕРКИ >>>

    stmt = select(Group).where(Group.id == group_id, Group.admin_user_id == current_user.id)
    group = (await db.execute(stmt)).scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Управляемое сообщество не найдено или у вас нет прав.")

    group_token = decrypt_data(group.encrypted_access_token)
    if not group_token:
        raise HTTPException(status_code=403, detail="Не удалось получить токен доступа для этого сообщества.")
        
    vk_api = VKAPI(access_token=group_token)
    try:
        attachments_str = ",".join(post_data.attachments)
        result = await vk_api.wall.post(
            owner_id=-group.vk_group_id,
            message=post_data.message,
            attachments=attachments_str,
            from_group=True
        )
        
        # <<< ДОБАВЛЕНО: Увеличиваем счетчик после успешной публикации >>>
        if result and result.get("post_id"):
            today_stats.posts_created_count += 1
            await db.commit() # Сохраняем изменение счетчика
            return {"status": "success", "post_id": result.get("post_id")}
        else:
            # Если по какой-то причине VK не вернул post_id, считаем это ошибкой
            raise VKAPIError(f"VK API не вернул ID поста. Ответ: {result}", 0)

    except VKAPIError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Ошибка VK API: {e.message}")
    finally:
        await vk_api.close()

async def get_group_vk_api(
    group_id: int,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
) -> VKAPI:
    """
    Зависимость для получения экземпляра VKAPI, инициализированного
    токеном доступа конкретного управляемого сообщества.
    """
    stmt = select(Group).where(Group.id == group_id, Group.admin_user_id == current_user.id)
    group = (await db.execute(stmt)).scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Управляемое сообщество не найдено или у вас нет прав.")

    group_token = decrypt_data(group.encrypted_access_token)
    if not group_token:
        raise HTTPException(status_code=403, detail="Не удалось получить токен доступа для этого сообщества.")
        
    return VKAPI(access_token=group_token)


# <<< НОВЫЕ ЭНДПОИНТЫ ДЛЯ ЗАГРУЗКИ ИЗОБРАЖЕНИЙ >>>

@router.post("/{group_id}/upload-image-file", response_model=UploadedImageResponse)
async def upload_group_image_file(
    group_id: int,
    vk_api: VKAPI = Depends(get_group_vk_api),
    image: UploadFile = File(...)
):
    """Загружает одно изображение с диска для поста в группе."""
    try:
        image_bytes = await image.read()
        attachment_id = await vk_api.photos.upload_for_wall(image_bytes)
        return UploadedImageResponse(attachment_id=attachment_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось загрузить изображение: {e}")
    finally:
        await vk_api.close()

@router.post("/{group_id}/upload-images-batch", response_model=UploadedImagesResponse)
async def upload_group_images_batch(
    group_id: int,
    vk_api: VKAPI = Depends(get_group_vk_api),
    images: List[UploadFile] = File(...)
):
    """Загружает несколько изображений с диска для поста в группе."""
    if len(images) > 10:
        raise HTTPException(status_code=400, detail="Можно загрузить не более 10 изображений за раз.")

    async def upload_one(image: UploadFile):
        try:
            image_bytes = await image.read()
            return await vk_api.photos.upload_for_wall(image_bytes)
        except Exception:
            return None

    try:
        tasks = [upload_one(img) for img in images]
        results = await asyncio.gather(*tasks)
        successful_attachments = [res for res in results if res is not None]
        
        if not successful_attachments:
            raise HTTPException(status_code=500, detail="Не удалось загрузить ни одно из изображений.")
            
        return UploadedImagesResponse(attachment_ids=successful_attachments)
    finally:
        await vk_api.close()


@router.post("/{group_id}/upload-image-from-url", response_model=UploadedImageResponse)
async def upload_group_image_from_url(
    group_id: int,
    image_url: HttpUrl,
    vk_api: VKAPI = Depends(get_group_vk_api)
):
    """Загружает одно изображение по URL для поста в группе."""
    try:
        image_bytes = await _download_image_from_url(str(image_url))
        attachment_id = await vk_api.photos.upload_for_wall(image_bytes)
        return UploadedImageResponse(attachment_id=attachment_id)
    except HTTPException as e:
        raise e # Пробрасываем HTTP исключения (например, 400 Bad Request от _download_image_from_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось обработать и загрузить изображение: {e}")
    finally:
        await vk_api.close()