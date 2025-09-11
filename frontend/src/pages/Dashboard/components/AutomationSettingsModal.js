// frontend/src/pages/Dashboard/components/AutomationSettingsModal.js
import React, { useState, useEffect } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, CircularProgress, Stack, Divider, Typography } from '@mui/material';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { updateAutomation } from 'api';
import { CommonFiltersSettings, RemoveFriendsFilters } from './ActionModalFilters';

const AutomationSettingsModal = ({ open, onClose, automation }) => {
    const queryClient = useQueryClient();
    const [settings, setSettings] = useState({});

    useEffect(() => {
        if (open && automation) {
            const defaults = {
                count: 50,
                filters: { sex: 0, is_online: false, allow_closed_profiles: false, remove_banned: true, last_seen_hours: 0, last_seen_days: 0, min_friends: 0, min_followers: 0 },
            };
            setSettings({ ...defaults, ...automation.settings });
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

    const handleSettingsChange = (nameOrEvent, value) => {
        let name, val;
        if (typeof nameOrEvent === 'string') {
            name = nameOrEvent;
            val = value;
        } else {
            const { target } = nameOrEvent;
            name = target.name;
            val = target.type === 'checkbox' ? target.checked : target.value;
        }

        const filterKeys = ['sex', 'is_online', 'allow_closed_profiles', 'remove_banned', 'last_seen_hours', 'last_seen_days', 'min_friends', 'min_followers'];

        if (filterKeys.includes(name)) {
            setSettings(s => ({ ...s, filters: { ...s.filters, [name]: val } }));
        } else {
            setSettings(s => ({ ...s, [name]: val }));
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

    const needsCount = ['like_feed', 'add_recommended', 'remove_friends', 'like_friends_feed'].includes(automation.automation_type);
    const needsFilters = !['view_stories', 'birthday_congratulation', 'eternal_online'].includes(automation.automation_type);

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
                            multiline
                            rows={4}
                            label="Шаблон поздравления"
                            name="message_template_default"
                            value={settings.message_template_default || ''}
                            onChange={handleSettingsChange}
                            helperText="Используйте {name} для подстановки имени друга."
                        />
                    )}

                    {needsCount && (
                        <TextField
                            fullWidth
                            type="number"
                            label="Количество действий за один запуск"
                            name="count"
                            value={settings.count || ''}
                            onChange={handleSettingsChange}
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