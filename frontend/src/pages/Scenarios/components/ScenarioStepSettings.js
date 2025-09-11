// frontend/src/pages/Scenarios/components/ScenarioStepSettings.js

import React from 'react';
import { Stack, Typography } from '@mui/material';
// toast и useUserStore больше не нужны в этом файле после рефакторинга
import ActionModalFilters from 'pages/Dashboard/components/ActionModalFilters'; // <--- ГЛАВНОЕ ИСПРАВЛЕНИЕ
import { content } from 'content/content';
import CountSlider from 'components/CountSlider';
import { useUserStore } from 'store/userStore'; // useUserStore все-таки нужен для лимитов

export const StepSettings = ({ step, onSettingsChange }) => {
    const userInfo = useUserStore(state => state.userInfo);

    const handleFieldChange = (name, value) => {
        // Обновляем настройки, сохраняя предыдущие значения
        const newSettings = { ...step.settings, [name]: value };
        onSettingsChange(newSettings);
    };

    const handleFilterChange = (name, value) => {
        const filterName = name.replace('filters.', '');
        const newFilters = { ...step.settings.filters, [filterName]: value };
        onSettingsChange({ ...step.settings, filters: newFilters });
    };

    const actionConfig = content.actions[step.action_type];
    const automationConfig = content.automations[step.action_type];

    if (!actionConfig || !automationConfig) return null;

    const hasSettings = !['view_stories', 'eternal_online'].includes(step.action_type);

    if (!hasSettings) {
        return <Typography variant="body2" color="text.secondary" sx={{ mt: 2, pl: 1 }}>Для этого действия нет дополнительных настроек.</Typography>;
    }
    
    const getLimit = () => {
        if (step.action_type.includes('add')) return userInfo?.daily_add_friends_limit || 100;
        if (step.action_type.includes('like')) return userInfo?.daily_likes_limit || 1000;
        // Для остальных задач ставим условный высокий лимит
        return 1000;
    };

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
        </Stack>
    );
};