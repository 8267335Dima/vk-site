from sqladmin import ModelView, action
from app.db.models.system import BannedIP
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

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
    async def unban_ips(self, request: Request, pks: list[int]):
        session: AsyncSession = request.state.session
        for pk in pks:
            ban = await session.get(BannedIP, int(pk))
            if ban:
                await session.delete(ban)
        await session.commit()
        return {"message": f"Разблокировано IP-адресов: {len(pks)}"}