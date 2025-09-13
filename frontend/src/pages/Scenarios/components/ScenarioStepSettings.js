// frontend/src/pages/Scenarios/components/ScenarioStepSettings.js
import React from 'react';
import { Stack, Typography, FormControl, Select, MenuItem, InputLabel } from '@mui/material';
import ActionModalFilters from 'pages/Dashboard/components/ActionModalFilters';
import { content } from 'content/content';
import CountSlider from 'components/CountSlider';
import { useUserStore } from 'store/userStore';

// --- ИСПРАВЛЕНИЕ: Этот код был по ошибке перемещен в другой файл. Теперь он на своем месте. ---
export const StepSettings = ({ step, onSettingsChange, onBatchChange }) => {
    const userInfo = useUserStore(state => state.userInfo);

    const handleFieldChange = (name, value) => {
        const newSettings = { ...step.settings, [name]: value };
        onSettingsChange(newSettings);
    };

    const handleFilterChange = (name, value) => {
        const filterName = name.replace('filters.', '');
        const newFilters = { ...step.settings.filters, [filterName]: value };
        onSettingsChange({ ...step.settings, filters: newFilters });
    };

    const actionConfig = content.actions[step.action_type];
    // --- ИСПРАВЛЕНИЕ: Правильный поиск конфига автоматизации в массиве ---
    const automationConfig = content.automations.find(a => a.id === step.action_type);

    if (!actionConfig || !automationConfig) return null;

    const hasSettings = !['view_stories', 'eternal_online'].includes(step.action_type);

    if (!hasSettings) {
        return <Typography variant="body2" color="text.secondary" sx={{ mt: 2, pl: 1 }}>Для этого действия нет дополнительных настроек.</Typography>;
    }
    
    const getLimit = () => {
        if (step.action_type.includes('add')) return userInfo?.daily_add_friends_limit || 100;
        if (step.action_type.includes('like')) return userInfo?.daily_likes_limit || 1000;
        return 1000;
    };
    
    const canBeBatched = ['add_recommended', 'like_feed', 'like_friends_feed', 'remove_friends'].includes(step.action_type);

    return (
        <Stack spacing={3} sx={{ mt: 2, p: 2, borderTop: '1px solid', borderColor: 'divider' }}>
            {actionConfig.modal_count_label && (
                <CountSlider
                    label={actionConfig.modal_count_label}
                    value={step.settings.count || 20}
                    onChange={(val) => handleFieldChange('count', val)}
                    max={getLimit()}
                />
            )}
            
            {automationConfig.has_filters && (
                 <ActionModalFilters 
                    filters={step.settings.filters || {}} 
                    onChange={handleFilterChange} 
                    actionKey={step.action_type} 
                />
            )}

            {canBeBatched && (
                <FormControl fullWidth size="small">
                    <InputLabel>Разбить выполнение</InputLabel>
                    <Select
                        value={step.batch_settings?.parts || 1}
                        label="Разбить выполнение"
                        onChange={(e) => onBatchChange(step.localId, { parts: e.target.value })}
                    >
                        <MenuItem value={1}>Не разбивать (выполнить за раз)</MenuItem>
                        <MenuItem value={2}>На 2 части</MenuItem>
                        <MenuItem value={3}>На 3 части</MenuItem>
                        <MenuItem value={4}>На 4 части</MenuItem>
                    </Select>
                </FormControl>
            )}
        </Stack>
    );
};