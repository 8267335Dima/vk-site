// frontend/src/pages/Dashboard/components/AutomationSettingsModal.js
import React, { useState, useEffect } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, CircularProgress, Stack, Divider, Typography } from '@mui/material';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { updateAutomation } from 'api';
import { CommonFiltersSettings, RemoveFriendsFilters } from './ActionModalFilters';
import CountSlider from 'components/CountSlider';
import { useUserStore } from 'store/userStore';
import { content } from 'content/content';

const AutomationSettingsModal = ({ open, onClose, automation }) => {
    const queryClient = useQueryClient();
    const [settings, setSettings] = useState({});
    const userInfo = useUserStore(state => state.userInfo);

    useEffect(() => {
        if (open && automation) {
            const defaults = {
                count: 50,
                filters: { sex: 0, is_online: false, allow_closed_profiles: false, remove_banned: true, last_seen_hours: 0, last_seen_days: 0, min_friends: null, max_friends: null, min_followers: null, max_followers: null },
                message_template_default: "С Днем Рождения, {name}! Желаю всего самого наилучшего, успехов и ярких моментов в жизни."
            };
            
            const mergedSettings = { ...defaults, ...automation.settings };
            
            if (automation.settings?.message_template_default) {
                mergedSettings.message_template_default = automation.settings.message_template_default;
            }

            setSettings(mergedSettings);
        }
    }, [open, automation]);

    const mutation = useMutation({
        mutationFn: updateAutomation,
        onSuccess: (updatedAutomation) => {
            queryClient.setQueryData(['automations'], (oldData) =>
                oldData.map(a => a.automation_type === updatedAutomation.automation_type ? updatedAutomation : a)
            );
            toast.success(`Настройки для "${updatedAutomation.name}" сохранены!`);
            onClose();
        },
        onError: (error) => toast.error(error.response?.data?.detail || 'Ошибка сохранения'),
    });

    const handleSettingsChange = (name, value) => {
        const filterKeys = ['sex', 'is_online', 'allow_closed_profiles', 'remove_banned', 'last_seen_hours', 'last_seen_days', 'min_friends', 'max_friends', 'min_followers', 'max_followers'];

        if (filterKeys.includes(name)) {
            setSettings(s => ({ ...s, filters: { ...s.filters, [name]: value } }));
        } else {
            setSettings(s => ({ ...s, [name]: value }));
        }
    };
    
    const handleSave = () => {
        mutation.mutate({
            automationType: automation.automation_type,
            isActive: automation.is_active,
            settings: settings,
        });
    };

    if (!automation) return null;

    const actionConfig = content.actions[automation.automation_type];
    const needsCount = actionConfig && !!actionConfig.modal_count_label;
    const needsFilters = !['view_stories', 'birthday_congratulation', 'eternal_online'].includes(automation.automation_type);
    
    const getLimit = () => {
        if (automation.automation_type.includes('add')) return userInfo?.daily_add_friends_limit || 100;
        if (automation.automation_type.includes('like')) return userInfo?.daily_likes_limit || 1000;
        return 1000;
    };

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
            <DialogTitle sx={{ fontWeight: 600 }}>Настройки: {automation.name}</DialogTitle>
            <DialogContent dividers>
                <Stack spacing={3} py={2}>
                    <Typography variant="body2" color="text.secondary">
                        Здесь вы можете задать параметры для автоматического выполнения задачи. Настройки сохраняются для каждого действия индивидуально.
                    </Typography>
                    
                    {automation.automation_type === 'birthday_congratulation' && (
                        <TextField
                            multiline rows={4} label="Шаблон поздравления" name="message_template_default"
                            value={settings.message_template_default || ''}
                            onChange={(e) => handleSettingsChange(e.target.name, e.target.value)}
                            helperText="Используйте {name} для подстановки имени друга."
                        />
                    )}

                    {needsCount && (
                        <CountSlider
                            label={actionConfig.modal_count_label}
                            value={settings.count || 20}
                            onChange={(val) => handleSettingsChange('count', val)}
                            max={getLimit()}
                        />
                    )}

                    {needsFilters && <Divider />}

                    {needsFilters && automation.automation_type === 'remove_friends' && (
                        <RemoveFriendsFilters filters={settings.filters || {}} onChange={handleSettingsChange} />
                    )}
                    {needsFilters && !['remove_friends'].includes(automation.automation_type) && (
                        <CommonFiltersSettings
                            filters={settings.filters || {}}
                            onChange={handleSettingsChange}
                            actionKey={automation.automation_type}
                        />
                    )}
                </Stack>
            </DialogContent>
            <DialogActions sx={{p: 2}}>
                <Button onClick={onClose}>Отмена</Button>
                <Button onClick={handleSave} variant="contained" disabled={mutation.isLoading}>
                    {mutation.isLoading ? <CircularProgress size={24} /> : 'Сохранить'}
                </Button>
            </DialogActions>
        </Dialog>
    );
};

export default AutomationSettingsModal;