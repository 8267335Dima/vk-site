// frontend/src/pages/Dashboard/components/UserProfileCard.js
import React from 'react';
import { Box, Paper, Link, Chip, Stack, Typography, Avatar, Grid, Button, Tooltip, Select, MenuItem, keyframes } from '@mui/material';
import { useQueryClient } from '@tanstack/react-query';
// ИСПРАВЛЕНО
import { useFeatureFlag } from '../../../hooks/useFeatureFlag';
import { useMutation } from '@tanstack/react-query';
// ИСПРАВЛЕНО
import { updateUserDelayProfile } from '../../../api';
import { toast } from 'react-hot-toast';

import WorkspacePremiumIcon from '@mui/icons-material/WorkspacePremium';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import SpeedIcon from '@mui/icons-material/Speed';
import ShutterSpeedIcon from '@mui/icons-material/ShutterSpeed';
import SlowMotionVideoIcon from '@mui/icons-material/SlowMotionVideo';

const pulseAnimation = keyframes`
  0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(50, 215, 75, 0.7); }
  70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(50, 215, 75, 0); }
  100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(50, 215, 75, 0); }
`;

const ConnectionStatusIndicator = ({ status }) => {
    
    const statusConfig = {
        'На связи': { label: 'Онлайн', color: 'success.main', animation: `${pulseAnimation} 2s infinite` },
        'Переподключение...': { label: 'Переподключение', color: 'warning.main' },
        'Отключено': { label: 'Отключено', color: 'error.main' },
        'Соединение...': { label: 'Соединение', color: 'info.main' },
    };
    
    const config = statusConfig[status] || { label: 'Неизвестно', color: 'text.secondary' };

    return (
        <Chip 
            label={config.label}
            size="small"
            sx={{
                '& .MuiChip-label': { fontWeight: 600 },
                '& .MuiChip-icon': {
                    color: config.color,
                    animation: config.animation,
                    borderRadius: '50%',
                    width: '10px',
                    height: '10px',
                },
            }}
            icon={<span />}
        />
    );
};

// ИЗМЕНЕНИЕ: Компонент обернут в React.memo для оптимизации
export const UserProfileCard = React.memo(({ userInfo, connectionStatus, onProxyManagerOpen }) => {
    const queryClient = useQueryClient();
    const { isFeatureAvailable } = useFeatureFlag();
    const canUseProxyManager = isFeatureAvailable('proxy_management');
    const canChangeSpeed = isFeatureAvailable('fast_slow_delay_profile');

    const mutation = useMutation({
        mutationFn: updateUserDelayProfile,
        onSuccess: (response) => { 
            // ИЗМЕНЕНИЕ: Обновляем данные в кэше React Query вместо вызова setUserInfo
            queryClient.setQueryData(['currentUser', userInfo.id], response);
            toast.success(`Скорость работы изменена!`); 
        },
        onError: () => toast.error("Не удалось изменить скорость.")
    });

    const handleSpeedChange = (event) => mutation.mutate({ delay_profile: event.target.value });

    return (
        <Paper sx={{ p: 3, display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, alignItems: 'center', gap: 3, height: '100%' }}>
            <Avatar src={userInfo.photo_200} sx={{ width: 100, height: 100, flexShrink: 0, border: '4px solid', borderColor: 'background.default', boxShadow: 3 }} />
            <Box flexGrow={1} width="100%">
                 <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1} sx={{mb: 1.5}}>
                     <Link href={`https://vk.com/id${userInfo.vk_id}`} target="_blank" color="text.primary" sx={{ textDecoration: 'none' }}>
                        <Typography variant="h5" sx={{ fontWeight: 700, '&:hover': { color: 'primary.main' } }}>{userInfo.first_name} {userInfo.last_name}</Typography>
                    </Link>
                    <ConnectionStatusIndicator status={connectionStatus} />
                </Stack>
                <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" sx={{ mb: 2 }}>
                    <Chip icon={<WorkspacePremiumIcon />} label={userInfo.plan} color="primary" variant="filled" size="small"/>
                    {userInfo.plan_expires_at && <Typography variant="caption" color="text.secondary">До {new Date(userInfo.plan_expires_at).toLocaleDateString('ru-RU')}</Typography>}
                </Stack>
                <Grid container spacing={1} alignItems="center">
                    <Grid item xs={12} sm={6} md={4}>
                         <Tooltip title={canUseProxyManager ? "Управление прокси" : "Доступно на PRO-тарифе"}>
                            <span>
                                <Button fullWidth size="small" startIcon={<VpnKeyIcon />} onClick={onProxyManagerOpen} disabled={!canUseProxyManager} variant="outlined" sx={{color: 'text.secondary'}}>Прокси</Button>
                            </span>
                        </Tooltip>
                    </Grid>
                    <Grid item xs={12} sm={6} md={8}>
                        <Tooltip title={!canChangeSpeed ? "Смена скорости доступна на PRO-тарифе" : ""}>
                            <Select
                                fullWidth size="small" value={userInfo.delay_profile} onChange={handleSpeedChange} disabled={mutation.isLoading || !canChangeSpeed}
                                renderValue={(value) => (
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        {value === 'fast' && <ShutterSpeedIcon fontSize="small" />}
                                        {value === 'normal' && <SpeedIcon fontSize="small" />}
                                        {value === 'slow' && <SlowMotionVideoIcon fontSize="small" />}
                                        {value === 'fast' && 'Быстрый'}
                                        {value === 'normal' && 'Стандарт'}
                                        {value === 'slow' && 'Медленный'}
                                    </Box>
                                )}>
                                <MenuItem value="slow"><SlowMotionVideoIcon sx={{mr: 1}}/> Медленный (Макс. безопасность)</MenuItem>
                                <MenuItem value="normal"><SpeedIcon sx={{mr: 1}}/> Стандарт (Баланс)</MenuItem>
                                <MenuItem value="fast"><ShutterSpeedIcon sx={{mr: 1}}/> Быстрый (Макс. скорость)</MenuItem>
                            </Select>
                        </Tooltip>
                    </Grid>
                </Grid>
            </Box>
        </Paper>
    );
});