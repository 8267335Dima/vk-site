# backend/app/admin/views/system.py
from sqladmin import ModelView
from app.db.models.system import GlobalSetting, BannedIP

class GlobalSettingsAdmin(ModelView, model=GlobalSetting):
    identity = "global-settings"
    name = "Настройка"
    name_plural = "Глобальные настройки"
    icon = "fa-solid fa-cogs"
    
    can_create = True
    can_delete = True
    can_edit = True
    
    column_list = [GlobalSetting.key, GlobalSetting.value, GlobalSetting.is_enabled, GlobalSetting.description]
    form_columns = [GlobalSetting.key, GlobalSetting.value, GlobalSetting.is_enabled, GlobalSetting.description]

class BannedIPAdmin(ModelView, model=BannedIP):
    identity = "banned-ips"
    name = "Блокировка"
    name_plural = "Заблокированные IP"
    icon = "fa-solid fa-gavel"
    
    can_create = True
    can_delete = True
    can_edit = True
    
    column_list = [BannedIP.ip_address, BannedIP.reason, BannedIP.banned_at, BannedIP.admin]
    column_searchable_list = [BannedIP.ip_address]
    column_default_sort = ("banned_at", True)