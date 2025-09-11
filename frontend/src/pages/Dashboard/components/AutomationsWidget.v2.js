// frontend/src/pages/Dashboard/components/AutomationsWidget.v2.js
import React from 'react';
import {
    Paper, Typography, Stack, Switch, Tooltip, Box,
    CircularProgress, Skeleton, IconButton, alpha
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchAutomations, updateAutomation } from 'api.js';
import { toast } from 'react-hot-toast';
import { content } from 'content/content';

const AutomationRow = ({ icon, name, description, automationKey, automationData, onToggle, onSettingsClick }) => {
    const isAvailable = automationData?.is_available ?? true;
    const isActive = automationData?.is_active ?? false;
    
    const handleToggle = (event) => {
        const newIsActive = event.target.checked;
        if (newIsActive && !isAvailable) {
            toast.error(`Эта функция недоступна на вашем тарифе.`);
            return;
        }
        onToggle.mutate({ automationType: automationKey, isActive: newIsActive, settings: automationData?.settings || {} });
    };
    
    const hasSettings = !['view_stories', 'eternal_online'].includes(automationKey);
    const isMutatingThisRow = onToggle.isLoading && onToggle.variables?.automationType === automationKey;

    return (
        <Stack
            direction="row" alignItems="center" justifyContent="space-between"
            sx={{
                p: 2, borderRadius: 3, bgcolor: 'background.default',
                border: '1px solid', borderColor: 'divider',
                opacity: isAvailable ? 1 : 0.6,
                transition: 'all 0.3s ease',
                '&:hover': { bgcolor: isAvailable ? (theme) => alpha(theme.palette.primary.main, 0.1) : 'background.default' }
            }}
        >
            <Stack direction="row" alignItems="center" spacing={2}>
                <Box sx={{ color: 'primary.main', fontSize: '1.8rem' }}>{icon}</Box>
                <Box>
                    <Typography component="div" variant="body1" sx={{ fontWeight: 600, display: 'flex', alignItems: 'center' }}>
                        {name}
                        <Tooltip title={description} placement="top" arrow>
                            <InfoOutlinedIcon sx={{ fontSize: '1rem', ml: 0.75, cursor: 'help', color: 'text.secondary' }} />
                        </Tooltip>
                    </Typography>
                </Box>
            </Stack>
            <Stack direction="row" alignItems="center" spacing={0.5}>
                {hasSettings && (
                    <IconButton size="small" disabled={!isAvailable || isMutatingThisRow} onClick={() => onSettingsClick(automationData)}>
                        <SettingsIcon fontSize="small" />
                    </IconButton>
                )}
                <Tooltip title={!isAvailable ? "Перейдите на PRO-тариф для доступа" : ""}>
                    <Box sx={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center', width: 40, height: 24 }}>
                        {isMutatingThisRow && <CircularProgress size={24} sx={{ position: 'absolute' }} />}
                        <Switch
                            checked={isActive}
                            onChange={handleToggle}
                            disabled={!isAvailable || isMutatingThisRow}
                            color="success"
                            sx={{ opacity: isMutatingThisRow ? 0 : 1 }}
                        />
                    </Box>
                </Tooltip>
            </Stack>
        </Stack>
    );
};

export default function AutomationsWidget({ onSettingsClick }) {
    const queryClient = useQueryClient();
    const { data: automationsData, isLoading } = useQuery({ queryKey: ['automations'], queryFn: fetchAutomations });

    const mutation = useMutation({
        mutationFn: updateAutomation,
        onSuccess: (updatedAutomation) => {
            queryClient.setQueryData(['automations'], (oldData) =>
                oldData.map(a => a.automation_type === updatedAutomation.automation_type ? updatedAutomation : a)
            );
            const statusText = updatedAutomation.is_active ? "активирована" : "остановлена";
            toast.success(`Автоматизация "${updatedAutomation.name}" ${statusText}!`);
        },
        onError: (error) => {
            toast.error(error?.response?.data?.detail || "Не удалось сохранить изменения.");
            queryClient.invalidateQueries({ queryKey: ['automations'] });
        },
    });

    return (
        <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, mb: 2 }}>Центр Автоматизации</Typography>
            <Stack spacing={2} sx={{ flexGrow: 1 }}>
                {isLoading ? (
                    Array.from(new Array(4)).map((_, index) => (
                        <Skeleton key={index} variant="rounded" height={68} sx={{ borderRadius: 3 }} />
                    ))
                ) : (
                    automationsData?.map(automation => {
                         const config = content.automations[automation.automation_type];
                         if (!config) return null;
                         return (
                            <AutomationRow
                                key={automation.automation_type}
                                icon={config.icon}
                                name={automation.name}
                                description={automation.description}
                                automationKey={automation.automation_type}
                                automationData={automation}
                                onToggle={mutation}
                                onSettingsClick={onSettingsClick}
                            />
                         )
                     })
                )}
            </Stack>
        </Paper>
    );
}