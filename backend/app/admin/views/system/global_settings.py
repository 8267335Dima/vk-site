from sqladmin import ModelView
from app.db.models.system import GlobalSetting

class GlobalSettingsAdmin(ModelView, model=GlobalSetting):
    category = "Система"
    name = "Настройка"
    name_plural = "Глобальные настройки"
    icon = "fa-solid fa-cogs"
    
    can_create = True
    can_delete = True
    can_edit = True

    column_list = [GlobalSetting.key, GlobalSetting.value, GlobalSetting.is_enabled, GlobalSetting.description]
    form_columns = [GlobalSetting.key, GlobalSetting.value, GlobalSetting.is_enabled, GlobalSetting.description]