// frontend/src/pages/Scenarios/components/ScenarioStepSettings.js
import React from 'react';
import { Stack, Typography, FormControl, Select, MenuItem, InputLabel } from '@mui/material';
// ИСПРАВЛЕНО: относительные пути
import { ActionModalFilters } from '../../Dashboard/components/ActionModal/ActionModalFilters'; 
import { content } from '../../../content/content';
import CountSlider from '../../../components/CountSlider';
import { useCurrentUser } from '../../../hooks/useCurrentUser'; // <-- Правильный хук

export const StepSettings = ({ step, onSettingsChange, onBatchChange }) => {
    const { data: userInfo } = useCurrentUser(); // <-- Получаем данные пользователя из React Query

    const handleFieldChange = (name, value) => {
        const newSettings = { ...step.settings, [name]: value };
        onSettingsChange(newSettings);
    };
    
    // Эта функция теперь не нужна, т.к. ActionModalFilters использует react-hook-form
    // и управляет своим состоянием самостоятельно.
    // onSettingsChange будет вызываться только для слайдера и других полей здесь.

    // ИСПРАВЛЕНО: Получаем конфиг по ключу из content.actions
    const actionConfig = content.actions[step.action_type];
    const automationConfig = content.automations.find(a => a.id === step.action_type);

    if (!actionConfig || !automationConfig) return null;

    const hasSettings = automationConfig.has_count_slider || automationConfig.has_filters;

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
            {automationConfig.has_count_slider && (
                <CountSlider
                    label={actionConfig.modal_count_label}
                    value={step.settings.count || 20}
                    onChange={(val) => handleFieldChange('count', val)}
                    max={getLimit()}
                />
            )}
            
            {automationConfig.has_filters && (
                 <ActionModalFilters 
                    actionKey={step.action_type} 
                    // Компонент теперь работает с react-hook-form, 
                    // ему не нужны пропсы filters и onChange
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