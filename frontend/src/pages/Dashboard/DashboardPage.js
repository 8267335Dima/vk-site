// frontend/src/pages/Dashboard/DashboardPage.js
import React, { Suspense, useState, lazy } from 'react';
import { Box, Paper, Link, Chip, Stack, Typography, Avatar, Grid, Button, Tooltip } from '@mui/material';
import { motion } from 'framer-motion';
import { formatDistanceToNow, format } from 'date-fns';
import { ru } from 'date-fns/locale';
import GroupIcon from '@mui/icons-material/Group';
import RssFeedIcon from '@mui/icons-material/RssFeed';
import WorkspacePremiumIcon from '@mui/icons-material/WorkspacePremium';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import EventBusyIcon from '@mui/icons-material/EventBusy';
import { useWebSocketContext } from 'contexts/WebSocketProvider';
import { useUserStore } from 'store/userStore';
import { useDashboardManager } from 'hooks/useDashboardManager';
import { dashboardContent } from 'content/dashboardContent';
import LazyLoader from 'components/LazyLoader';
import { is_feature_available as isFeatureAvailable } from 'utils/planUtils';

import ActionPanel from './components/ActionPanel';
import EventFeed from './components/EventFeed';
import ActionModal from './components/ActionModal';

// Ленивая загрузка виджетов
const AutomationsWidget = lazy(() => import('./components/AutomationsWidget'));
const LimitsWidget = lazy(() => import('./components/LimitsWidget'));
const ActivityChartWidget = lazy(() => import('./components/ActivityChartWidget'));
const AudienceAnalyticsWidget = lazy(() => import('./components/AudienceAnalyticsWidget')); 
const FriendsDynamicWidget = lazy(() => import('./components/FriendsDynamicWidget'));
const ProxyManagerModal = lazy(() => import('./components/ProxyManagerModal'));
const AutomationSettingsModal = lazy(() => import('./components/AutomationSettingsModal'));
const ActionSummaryWidget = lazy(() => import('./components/ActionSummaryWidget'));
const FriendsAnalyticsWidget = lazy(() => import('./components/FriendsAnalyticsWidget'));


const motionVariants = {
    initial: { opacity: 0, y: 20 },
    animate: (i) => ({ opacity: 1, y: 0, transition: { delay: i * 0.1, duration: 0.5, ease: "easeOut" } }),
};

const UserProfileCard = ({ userInfo, connectionStatus, onProxyManagerOpen }) => {
    const canUseProxyManager = isFeatureAvailable(userInfo.plan, 'proxy_management');
    
    const PlanInfo = () => {
        const expiresDate = userInfo.plan_expires_at ? new Date(userInfo.plan_expires_at) : null;
        const isExpired = !userInfo.is_plan_active;

        if (isExpired) {
            return ( <Chip icon={<EventBusyIcon />} label="Тариф неактивен" color="error" variant="filled" size="small" /> );
        }
        
        const distance = formatDistanceToNow(expiresDate, { locale: ru, addSuffix: true });

        return (
            <Tooltip title={`Тариф активен до ${format(expiresDate, 'd MMMM yyyy, HH:mm', { locale: ru })}`} arrow>
                 <Chip icon={<WorkspacePremiumIcon />} label={`${userInfo.plan} (осталось ${distance})`} color="primary" variant="filled" size="small"/>
            </Tooltip>
        );
    };

    return (
        <Paper sx={{ p: 3, display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, alignItems: 'center', gap: 3, height: '100%' }}>
            <Avatar src={userInfo.photo_200} sx={{ width: 100, height: 100, flexShrink: 0, border: '4px solid', borderColor: 'background.default', boxShadow: 3 }} />
            <Box flexGrow={1} width="100%">
                <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1} sx={{mb: 1.5}}>
                     <Link href={`https://vk.com/id${userInfo.id}`} target="_blank" color="text.primary" sx={{ textDecoration: 'none' }}>
                        <Typography variant="h5" sx={{ fontWeight: 700 }}>{userInfo.first_name} {userInfo.last_name}</Typography>
                    </Link>
                    <Chip label={connectionStatus} color={connectionStatus === 'Live' ? 'success' : 'warning'} size="small" sx={{ flexShrink: 0, mt: 0.5 }} />
                </Stack>
                
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2, fontStyle: 'italic', wordBreak: 'break-word', minHeight: '20px' }}>
                    {userInfo.status || dashboardContent.profile.noStatus}
                </Typography>

                <Stack direction="row" spacing={1.5} flexWrap="wrap" useGap>
                    <PlanInfo />
                    <Chip icon={<GroupIcon />} label={`${userInfo.counters?.friends || '0'} друзей`} size="small" variant="outlined"/>
                    <Chip icon={<RssFeedIcon />} label={`${userInfo.counters?.followers || '0'} подписчиков`} size="small" variant="outlined"/>
                    {/* --- ИСПРАВЛЕНИЕ: УДАЛЕНЫ ЧИПЫ С ФОТО И ВИДЕО --- */}
                    <Tooltip title={canUseProxyManager ? "Управление прокси" : "Доступно на PRO-тарифе"} arrow>
                        <span>
                          <Button size="small" startIcon={<VpnKeyIcon />} onClick={onProxyManagerOpen} disabled={!canUseProxyManager} variant="text" sx={{color: 'text.secondary'}}>
                              Прокси
                          </Button>
                        </span>
                    </Tooltip>
                </Stack>
            </Box>
        </Paper>
    );
};

export default function DashboardPage() {
    const userInfo = useUserStore(state => state.userInfo);
    const wsContext = useWebSocketContext();
    const connectionStatus = wsContext ? wsContext.connectionStatus : 'Подключение...';
    const { modalState, openModal, closeModal, onActionSubmit } = useDashboardManager();
    const [isProxyModalOpen, setProxyModalOpen] = useState(false);
    const [automationToEdit, setAutomationToEdit] = useState(null);

    if (!userInfo) return <LazyLoader />;

    return (
        <Box sx={{ py: 4, px: { xs: 0, sm: 1, lg: 2 } }}>
            <Grid container spacing={4}>
                {/* Левая колонка */}
                <Grid item xs={12} lg={4}>
                    <Stack spacing={4}>
                        <motion.div custom={0} variants={motionVariants} initial="initial" animate="animate">
                           <ActionPanel onConfigure={openModal} />
                        </motion.div>
                         <motion.div custom={1} variants={motionVariants} initial="initial" animate="animate">
                           <Suspense fallback={<LazyLoader variant="skeleton" height="300px" />}>
                                <AutomationsWidget onSettingsClick={(automation) => setAutomationToEdit(automation)} />
                            </Suspense>
                        </motion.div>
                         <motion.div custom={8} variants={motionVariants} initial="initial" animate="animate">
                             <EventFeed />
                        </motion.div>
                    </Stack>
                </Grid>
                
                {/* Правая колонка */}
                <Grid item xs={12} lg={8}>
                    <Stack spacing={4}>
                        <motion.div custom={2} variants={motionVariants} initial="initial" animate="animate">
                            <UserProfileCard userInfo={userInfo} connectionStatus={connectionStatus} onProxyManagerOpen={() => setProxyModalOpen(true)} />
                        </motion.div>
                         <Grid container spacing={4}>
                           <Grid item xs={12} md={6}>
                                <motion.div custom={3} variants={motionVariants} initial="initial" animate="animate" style={{height: '100%'}}>
                                   <Suspense fallback={<LazyLoader variant="skeleton" height="250px" />}>
                                        <LimitsWidget />
                                    </Suspense>
                                </motion.div>
                            </Grid>
                            <Grid item xs={12} md={6}>
                                <motion.div custom={4} variants={motionVariants} initial="initial" animate="animate" style={{height: '100%'}}>
                                    <Suspense fallback={<LazyLoader variant="skeleton" height="300px" />}>
                                        {/* --- ИСПРАВЛЕНИЕ: ДОБАВЛЕН FriendsAnalyticsWidget, КОТОРЫЙ ИСПОЛЬЗОВАЛСЯ, НО НЕ БЫЛ ИМПОРТИРОВАН --- */}
                                        <FriendsAnalyticsWidget />
                                    </Suspense>
                                </motion.div>
                            </Grid>
                        </Grid>
                        {/* --- ИСПРАВЛЕНИЕ: ДОБАВЛЕН AudienceAnalyticsWidget, КОТОРЫЙ БЫЛ ИМПОРТИРОВАН, НО НЕ ИСПОЛЬЗОВАЛСЯ --- */}
                        <motion.div custom={4} variants={motionVariants} initial="initial" animate="animate">
                           <Suspense fallback={<LazyLoader variant="skeleton" height="300px" />}>
                                <AudienceAnalyticsWidget />
                           </Suspense>
                        </motion.div>
                        <motion.div custom={5} variants={motionVariants} initial="initial" animate="animate">
                            <Suspense fallback={<LazyLoader variant="skeleton" height="400px" />}>
                                <ActivityChartWidget />
                            </Suspense>
                        </motion.div>
                        <motion.div custom={6} variants={motionVariants} initial="initial" animate="animate">
                           <Suspense fallback={<LazyLoader variant="skeleton" height="250px" />}>
                                <ActionSummaryWidget />
                           </Suspense>
                        </motion.div>
                        <motion.div custom={7} variants={motionVariants} initial="initial" animate="animate">
                           <Suspense fallback={<LazyLoader variant="skeleton" height="250px" />}>
                                <FriendsDynamicWidget />
                           </Suspense>
                        </motion.div>
                    </Stack>
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