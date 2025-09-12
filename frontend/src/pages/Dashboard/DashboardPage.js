import React, { Suspense, useState, lazy, memo } from 'react';
import { Box, Paper, Link, Chip, Stack, Typography, Avatar, Grid, Button, Tooltip, Select, MenuItem, useTheme } from '@mui/material';
import { motion } from 'framer-motion';

// Hooks & State Management
import { useUserStore, useUserActions } from 'store/userStore';
import { useDashboardManager } from 'hooks/useDashboardManager';
import { useFeatureFlag } from 'hooks/useFeatureFlag';
import { useMutation } from '@tanstack/react-query';

// API & Utils
import { updateUserDelayProfile } from 'api';
import { toast } from 'react-hot-toast';

// Components
import LazyLoader from 'components/LazyLoader';
// --- ИЗМЕНЕНИЕ: Заменяем относительные пути на абсолютные для надежности ---
import ActionModal from 'pages/Dashboard/components/ActionModal';
import TaskLogWidget from 'pages/Dashboard/components/TaskLogWidget';
import ProfileSummaryWidget from 'pages/Dashboard/components/ProfileSummaryWidget';
import UnifiedActionPanel from 'pages/Dashboard/components/UnifiedActionPanel';

// Icons
import WorkspacePremiumIcon from '@mui/icons-material/WorkspacePremium';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import SpeedIcon from '@mui/icons-material/Speed';
import ShutterSpeedIcon from '@mui/icons-material/ShutterSpeed';
import SlowMotionVideoIcon from '@mui/icons-material/SlowMotionVideo';
import WifiIcon from '@mui/icons-material/Wifi';
import PowerSettingsNewIcon from '@mui/icons-material/PowerSettingsNew';

// --- ИЗМЕНЕНИЕ: Заменяем относительные пути на абсолютные в ленивых импортах ---
const ActivityChartWidget = lazy(() => import('pages/Dashboard/components/ActivityChartWidget'));
const AudienceAnalyticsWidget = lazy(() => import('pages/Dashboard/components/AudienceAnalyticsWidget'));
const ProfileGrowthWidget = lazy(() => import('pages/Dashboard/components/ProfileGrowthWidget'));
const ProxyManagerModal = lazy(() => import('pages/Dashboard/components/ProxyManagerModal'));
const AutomationSettingsModal = lazy(() => import('pages/Dashboard/components/AutomationSettingsModal'));

// Animation Variants
const motionVariants = {
    initial: { opacity: 0, y: 20 },
    animate: (i) => ({ opacity: 1, y: 0, transition: { delay: i * 0.1, duration: 0.5, ease: "easeOut" } }),
};

const UserProfileCard = memo(({ userInfo, connectionStatus, onProxyManagerOpen }) => {
    const theme = useTheme();
    const { isFeatureAvailable } = useFeatureFlag();
    const { setUserInfo } = useUserActions();
    const canUseProxyManager = isFeatureAvailable('proxy_management');
    const canChangeSpeed = isFeatureAvailable('fast_slow_delay_profile');

    const mutation = useMutation({
        mutationFn: updateUserDelayProfile,
        onSuccess: (response) => {
            setUserInfo(response.data);
            toast.success(`Скорость работы изменена!`);
        },
        onError: () => toast.error("Не удалось изменить скорость.")
    });

    const handleSpeedChange = (event) => {
        mutation.mutate({ delay_profile: event.target.value });
    };

    const isConnected = connectionStatus === 'На связи';

    return (
        <Paper sx={{ p: 3, display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, alignItems: 'center', gap: 3, height: '100%' }}>
            <Avatar src={userInfo.photo_200} sx={{ width: 100, height: 100, flexShrink: 0, border: '4px solid', borderColor: theme.palette.background.default, boxShadow: 3 }} />
            <Box flexGrow={1} width="100%">
                 <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1} sx={{mb: 1.5}}>
                     <Link href={`https://vk.com/id${userInfo.vk_id}`} target="_blank" color="text.primary" sx={{ textDecoration: 'none' }}>
                        <Typography variant="h5" sx={{ fontWeight: 700, '&:hover': { color: 'primary.main' } }}>{userInfo.first_name} {userInfo.last_name}</Typography>
                    </Link>
                    <Chip 
                        label={connectionStatus} 
                        icon={isConnected ? <WifiIcon/> : <PowerSettingsNewIcon/>} 
                        color={isConnected ? 'success' : 'warning'} 
                        size="small" 
                        sx={{ flexShrink: 0, mt: 0.5 }} 
                    />
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

export default function DashboardPage() {
    const userInfo = useUserStore(state => state.userInfo);
    const connectionStatus = useUserStore(state => state.connectionStatus);
    const { isFeatureAvailable } = useFeatureFlag();
    const { modalState, openModal, closeModal, onActionSubmit } = useDashboardManager();
    const [isProxyModalOpen, setProxyModalOpen] = useState(false);
    const [automationToEdit, setAutomationToEdit] = useState(null);

    if (!userInfo) {
        return <LazyLoader />;
    }

    return (
        <Box sx={{ py: 4, px: { xs: 1, sm: 2, lg: 3 } }}>
             <motion.div custom={0} variants={motionVariants} initial="initial" animate="animate">
                <Typography variant="h4" component="h1" sx={{ fontWeight: 700, mb: 3 }}>
                    Панель управления
                </Typography>
            </motion.div>
            
            <Grid container spacing={3}>
                {/* Левая колонка */}
                <Grid item xs={12} lg={4}>
                    <motion.div custom={1} variants={motionVariants} initial="initial" animate="animate" style={{ height: '100%' }}>
                       <UnifiedActionPanel onRun={openModal} onSettings={setAutomationToEdit} />
                    </motion.div>
                </Grid>
                
                {/* Правая колонка */}
                <Grid item xs={12} lg={8}>
                    <Stack spacing={3}>
                        <motion.div custom={2} variants={motionVariants} initial="initial" animate="animate">
                            <UserProfileCard userInfo={userInfo} connectionStatus={connectionStatus} onProxyManagerOpen={() => setProxyModalOpen(true)} />
                        </motion.div>
                         <motion.div custom={2.5} variants={motionVariants} initial="initial" animate="animate">
                             <Suspense fallback={<LazyLoader />}>
                                 <ProfileSummaryWidget />
                             </Suspense>
                         </motion.div>
                        <motion.div custom={3} variants={motionVariants} initial="initial" animate="animate">
                            <Suspense fallback={<LazyLoader />}>
                                <ActivityChartWidget />
                            </Suspense>
                        </motion.div>
                        {isFeatureAvailable('profile_growth_analytics') && (
                            <motion.div custom={4} variants={motionVariants} initial="initial" animate="animate">
                               <Suspense fallback={<LazyLoader />}>
                                    <ProfileGrowthWidget />
                               </Suspense>
                            </motion.div>
                        )}
                        <motion.div custom={5} variants={motionVariants} initial="initial" animate="animate">
                           <Suspense fallback={<LazyLoader />}>
                                <AudienceAnalyticsWidget />
                           </Suspense>
                        </motion.div>
                    </Stack>
                </Grid>

                {/* Нижний блок на всю ширину */}
                <Grid item xs={12}>
                    <motion.div custom={6} variants={motionVariants} initial="initial" animate="animate">
                         <TaskLogWidget />
                    </motion.div>
                </Grid>
            </Grid>
            
            <ActionModal {...modalState} onClose={closeModal} onSubmit={onActionSubmit} />
            <Suspense>
                {isProxyModalOpen && <ProxyManagerModal open={isProxyModalOpen} onClose={() => setProxyModalOpen(false)} />}
                {automationToEdit && <AutomationSettingsModal open={!!automationToEdit} onClose={() => setAutomationToEdit(null)} automation={automationToEdit} />}
            </Suspense>
        </Box>
    );
}