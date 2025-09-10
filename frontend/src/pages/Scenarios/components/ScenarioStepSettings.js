// frontend/src/pages/Scenarios/components/ScenarioStepSettings.js
import React from 'react';
import { Stack, TextField, Typography } from '@mui/material';
import { toast } from 'react-hot-toast';
import { useUserStore } from 'store/userStore';
import { CommonFiltersSettings, RemoveFriendsFilters } from 'pages/Dashboard/components/ActionModalFilters';
import { actionOptions } from './constants';

export const StepSettings = ({ step, onSettingsChange }) => {
    const userInfo = useUserStore(state => state.userInfo);
    const friendsCount = userInfo?.counters?.friends || 0;

    const handleFieldChange = (e) => {
        let { name, value } = e.target;
        
        if (name === 'count') {
            let numericValue = parseInt(value, 10) || 0;
            let limit = Infinity;

            if (step.action_type.includes('add')) {
                limit = userInfo?.daily_add_friends_limit;
            } else if (step.action_type.includes('like')) {
                limit = userInfo?.daily_likes_limit;
            } else if (step.action_type === 'remove_friends') {
                limit = friendsCount;
            }

            if (limit && numericValue > limit) {
                numericValue = limit;
                toast.info(`Максимальное значение для вашего тарифа: ${limit}`);
            }
            onSettingsChange({ ...step.settings, [name]: numericValue });
        } else {
            onSettingsChange({ ...step.settings, [name]: value });
        }
    };

    const handleFilterChange = (e) => {
        const { name, value, type, checked } = e.target;
        const newFilters = { ...step.settings.filters, [name]: type === 'checkbox' ? checked : value };
        onSettingsChange({ ...step.settings, filters: newFilters });
    };

    const actionConfig = actionOptions.find(opt => opt.key === step.action_type);
    const hasSettings = !['view_stories'].includes(step.action_type);

    if (!hasSettings) {
        return <Typography variant="body2" color="text.secondary" sx={{ mt: 2, pl: 1 }}>Для этого действия нет дополнительных настроек.</Typography>;
    }

    return (
        <Stack spacing={2} sx={{ mt: 2, p: 2, borderTop: '1px solid', borderColor: 'divider' }}>
            {actionConfig?.countLabel && (
                <TextField size="small" label={actionConfig.countLabel} type="number" name="count" value={step.settings.count || 20} onChange={handleFieldChange} />
            )}
            
            {step.action_type === 'remove_friends' ? (
                <RemoveFriendsFilters filters={step.settings.filters || {}} onChange={handleFilterChange} />
            ) : (
                <CommonFiltersSettings filters={step.settings.filters || {}} onChange={handleFilterChange} actionKey={step.action_type} />
            )}
        </Stack>
    );
};