// frontend/src/pages/Dashboard/DashboardPage.js

import React, { Suspense, useState, lazy } from 'react';
import { Box, Paper, Link, Chip, Stack, Typography, Avatar, Grid, Button, Tooltip, Select, MenuItem } from '@mui/material';
import { motion } from 'framer-motion';

// Icons
import GroupIcon from '@mui/icons-material/Group';
import RssFeedIcon from '@mui/icons-material/RssFeed';
import WorkspacePremiumIcon from '@mui/icons-material/WorkspacePremium';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import SpeedIcon from '@mui/icons-material/Speed';
import ShutterSpeedIcon from '@mui/icons-material/ShutterSpeed';
import SlowMotionVideoIcon from '@mui/icons-material/SlowMotionVideo';

// Hooks & State Management
import { useWebSocketContext } from 'contexts/WebSocketProvider';
import { useUserStore } from 'store/userStore';
import { useDashboardManager } from 'hooks/useDashboardManager';
import { useFeatureFlag } from 'hooks/useFeatureFlag'; // <-- Централизованная проверка прав
import { useMutation } from '@tanstack/react-query';

// API & Utils
import { updateUserDelayProfile } from 'api';
import { toast } from 'react-hot-toast';

// Components
import LazyLoader from 'components/LazyLoader';
import ActionPanel from './components/ActionPanel';
import ActionModal from './components/ActionModal';
import TaskLogWidget from './components/TaskLogWidget';

// Lazy-loaded Widgets
const AutomationsWidget = lazy(() => import('./components/AutomationsWidget.v2'));
const ActivityChartWidget = lazy(() => import('./components/ActivityChartWidget'));
const AudienceAnalyticsWidget = lazy(() => import('./components/AudienceAnalyticsWidget'));
const ProfileGrowthWidget = lazy(() => import('./components/ProfileGrowthWidget'));
const ProxyManagerModal = lazy(() => import('./components/ProxyManagerModal'));
const AutomationSettingsModal = lazy(() => import('./components/AutomationSettingsModal'));

// Animation Variants
const motionVariants = {
    initial: { opacity: 0, y: 20 },
    animate: (i) => ({ opacity: 1, y: 0, transition: { delay: i * 0.1, duration: 0.5, ease: "easeOut" } }),
};

const UserProfileCard = ({ userInfo, connectionStatus, onProxyManagerOpen }) => {
    // --- ИСПРАВЛЕНИЕ: Используем хук useFeatureFlag для проверки прав ---
    const { isFeatureAvailable } = useFeatureFlag();
    const canUseProxyManager = isFeatureAvailable('proxy_management');
    const canChangeSpeed = isFeatureAvailable('fast_slow_delay_profile');

    const mutation = useMutation({
        mutationFn: updateUserDelayProfile,
        onSuccess: (response) => {
            useUserStore.getState().setUserInfo(response.data);
            toast.success(`Скорость работы изменена!`);
        },
        onError: () => toast.error("Не удалось изменить скорость.")
    });

    const handleSpeedChange = (event) => {
        // Передаем объект, как ожидает API-эндпоинт
        mutation.mutate({ delay_profile: event.target.value });
    };

    return (
        <Paper sx={{ p: 3, display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, alignItems: 'center', gap: 3, height: '100%' }}>
            <Avatar src={userInfo.photo_200} sx={{ width: 100, height: 100, flexShrink: 0, border: '4px solid', borderColor: 'background.default', boxShadow: 3 }} />
            <Box flexGrow={1} width="100%">
                <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1} sx={{mb: 1.5}}>
                     <Link href={`https://vk.com/id${userInfo.vk_id}`} target="_blank" color="text.primary" sx={{ textDecoration: 'none' }}>
                        <Typography variant="h5" sx={{ fontWeight: 700 }}>{userInfo.first_name} {userInfo.last_name}</Typography>
                    </Link>
                    <Chip label={connectionStatus} color={connectionStatus === 'Live' ? 'success' : 'warning'} size="small" sx={{ flexShrink: 0, mt: 0.5 }} />
                </Stack>

                <Stack direction="row" spacing={1.5} flexWrap="wrap" useGap sx={{ mb: 2 }}>
                    <Chip icon={<WorkspacePremiumIcon />} label={`${userInfo.plan}`} color="primary" variant="filled" size="small"/>
                    <Chip icon={<GroupIcon />} label={`${userInfo.counters?.friends || '0'} друзей`} size="small" variant="outlined"/>
                    <Chip icon={<RssFeedIcon />} label={`${userInfo.counters?.followers || '0'} подписчиков`} size="small" variant="outlined"/>
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
                        <Tooltip title={!canChangeSpeed && userInfo.delay_profile !== 'normal' ? "Смена скорости доступна на PRO-тарифе" : ""}>
                            <Select
                                fullWidth
                                size="small"
                                value={userInfo.delay_profile}
                                onChange={handleSpeedChange}
                                disabled={mutation.isLoading}
                                renderValue={(value) => (
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        {value === 'fast' && <ShutterSpeedIcon fontSize="small" />}
                                        {value === 'normal' && <SpeedIcon fontSize="small" />}
                                        {value === 'slow' && <SlowMotionVideoIcon fontSize="small" />}
                                        {value === 'fast' && 'Быстрый'}
                                        {value === 'normal' && 'Нормальный'}
                                        {value === 'slow' && 'Медленный'}
                                    </Box>
                                )}
                            >
                                <MenuItem value="slow" disabled={!canChangeSpeed}>
                                    <SlowMotionVideoIcon sx={{mr: 1}}/> Медленный (Макс. безопасность)
                                </MenuItem>
                                <MenuItem value="normal">
                                    <SpeedIcon sx={{mr: 1}}/> Нормальный (Баланс)
                                </MenuItem>
                                <MenuItem value="fast" disabled={!canChangeSpeed}>
                                    <ShutterSpeedIcon sx={{mr: 1}}/> Быстрый (Макс. скорость)
                                </MenuItem>
                            </Select>
                        </Tooltip>
                    </Grid>
                </Grid>
            </Box>
        </Paper>
    );
};

export default function DashboardPage() {
    const userInfo = useUserStore(state => state.userInfo);
    const { isFeatureAvailable } = useFeatureFlag();
    const { connectionStatus } = useWebSocketContext() || { connectionStatus: 'Подключение...' };
    const { modalState, openModal, closeModal, onActionSubmit } = useDashboardManager();
    const [isProxyModalOpen, setProxyModalOpen] = useState(false);
    const [automationToEdit, setAutomationToEdit] = useState(null);

    if (!userInfo) {
        return <LazyLoader />;
    }

    return (
        <Box sx={{ py: 4, px: { xs: 1, sm: 2, lg: 3 } }}>
            {/* --- Приветствие --- */}
            <motion.div custom={0} variants={motionVariants} initial="initial" animate="animate">
                <Typography variant="h4" component="h1" sx={{ fontWeight: 700, mb: 3 }}>
                    Здравствуйте, {userInfo.first_name}!
                </Typography>
            </motion.div>
            
            <Grid container spacing={3}>
                {/* ====== Левая колонка: Управление ====== */}
                <Grid item xs={12} lg={4}>
                    <Stack spacing={3}>
                        <motion.div custom={1} variants={motionVariants} initial="initial" animate="animate">
                           <ActionPanel onConfigure={openModal} />
                        </motion.div>
                         <motion.div custom={2} variants={motionVariants} initial="initial" animate="animate">
                           <Suspense fallback={<LazyLoader />}>
                                <AutomationsWidget onSettingsClick={setAutomationToEdit} />
                            </Suspense>
                        </motion.div>
                    </Stack>
                </Grid>
                
                {/* ====== Правая колонка: Аналитика ====== */}
                <Grid item xs={12} lg={8}>
                    <Stack spacing={3}>
                        <motion.div custom={3} variants={motionVariants} initial="initial" animate="animate">
                            <UserProfileCard userInfo={userInfo} connectionStatus={connectionStatus} onProxyManagerOpen={() => setProxyModalOpen(true)} />
                        </motion.div>
                        
                        <motion.div custom={4} variants={motionVariants} initial="initial" animate="animate">
                            <Suspense fallback={<LazyLoader />}>
                                <ActivityChartWidget />
                            </Suspense>
                        </motion.div>
                        
                        {isFeatureAvailable('profile_growth_analytics') && (
                            <motion.div custom={5} variants={motionVariants} initial="initial" animate="animate">
                               <Suspense fallback={<LazyLoader />}>
                                    <ProfileGrowthWidget />
                               </Suspense>
                            </motion.div>
                        )}
                        
                        <motion.div custom={6} variants={motionVariants} initial="initial" animate="animate">
                           <Suspense fallback={<LazyLoader />}>
                                <AudienceAnalyticsWidget />
                           </Suspense>
                        </motion.div>
                    </Stack>
                </Grid>

                 {/* ====== Нижний блок: Журнал задач ====== */}
                <Grid item xs={12}>
                    <motion.div custom={7} variants={motionVariants} initial="initial" animate="animate">
                         <TaskLogWidget />
                    </motion.div>
                </Grid>
            </Grid>
            
            {/* ====== Модальные окна ====== */}
            <ActionModal {...modalState} onClose={closeModal} onSubmit={onActionSubmit} />
            <Suspense>
                {isProxyModalOpen && <ProxyManagerModal open={isProxyModalOpen} onClose={() => setProxyModalOpen(false)} />}
                {automationToEdit && <AutomationSettingsModal open={!!automationToEdit} onClose={() => setAutomationToEdit(null)} automation={automationToEdit} />}
            </Suspense>
        </Box>
    );
}