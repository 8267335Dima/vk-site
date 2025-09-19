# backend/app/admin/views/system/banned_ip.py

from sqladmin import ModelView, action
from app.db.models.system import BannedIP
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class BannedIPAdmin(ModelView, model=BannedIP):
    category = "Система"
    name = "Блокировка IP"
    name_plural = "Заблокированные IP"
    icon = "fa-solid fa-gavel"
    
    can_create = True
    can_delete = True
    can_edit = True

    column_list = [BannedIP.ip_address, BannedIP.reason, BannedIP.banned_at, BannedIP.admin]
    column_searchable_list = [BannedIP.ip_address]
    column_default_sort = ("banned_at", True)

    @action(name="unban_ips", label="🟢 Разблокировать")
    async def unban_ips(self, request: Request, pks: list[int]) -> JSONResponse:
        session: AsyncSession = request.state.session
        pks_int = [int(pk) for pk in pks]
        if pks_int:
            result = await session.execute(select(BannedIP).where(BannedIP.id.in_(pks_int)))
            for ip_ban in result.scalars().all():
                await session.delete(ip_ban)
            await session.commit()
        return JSONResponse(content={"message": f"Разблокировано IP-адресов: {len(pks)}"})