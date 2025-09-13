// --- frontend/src/pages/Dashboard/DashboardPage.js ---
import React, { Suspense, useState, lazy, useEffect } from 'react';
import { Box, Grid, Typography, motion, Stack } from '@mui/material'; // ИЗМЕНЕНИЕ: Оставлены только используемые компоненты
import Joyride, { STATUS } from 'react-joyride';

import { useUserStore } from 'store/userStore';
import { useCurrentUser } from 'hooks/useCurrentUser';
import { useDashboardManager } from 'hooks/useDashboardManager';
import { useFeatureFlag } from 'hooks/useFeatureFlag';

import LazyLoader from 'components/LazyLoader';
import ActionModal from 'pages/Dashboard/components/ActionModal';
import TaskLogWidget from 'pages/Dashboard/components/TaskLogWidget';
import ProfileSummaryWidget from 'pages/Dashboard/components/ProfileSummaryWidget';
import UnifiedActionPanel from 'pages/Dashboard/components/UnifiedActionPanel';
import { UserProfileCard } from './components/UserProfileCard'; // Компонент теперь импортируется отсюда

// ИЗМЕНЕНИЕ: Все неиспользуемые импорты иконок и утилит удалены

const ActivityChartWidget = lazy(() => import('pages/Dashboard/components/ActivityChartWidget'));
const AudienceAnalyticsWidget = lazy(() => import('pages/Dashboard/components/AudienceAnalyticsWidget'));
const ProfileGrowthWidget = lazy(() => import('pages/Dashboard/components/ProfileGrowthWidget'));
const ProxyManagerModal = lazy(() => import('pages/Dashboard/components/ProxyManagerModal'));
const AutomationSettingsModal = lazy(() => import('pages/Dashboard/components/AutomationSettingsModal'));
const FriendRequestConversionWidget = lazy(() => import('pages/Dashboard/components/FriendRequestConversionWidget'));
const PostActivityHeatmapWidget = lazy(() => import('pages/Dashboard/components/PostActivityHeatmapWidget'));

const motionVariants = {
    initial: { opacity: 0, y: 20 },
    animate: (i) => ({ opacity: 1, y: 0, transition: { delay: i * 0.1, duration: 0.5, ease: "easeOut" } }),
};

export default function DashboardPage() {
    const { data: userInfo, isLoading: isUserLoading } = useCurrentUser();
    const connectionStatus = useUserStore(state => state.connectionStatus);
    const { isFeatureAvailable } = useFeatureFlag();
    const { modalState, openModal, closeModal, onActionSubmit } = useDashboardManager();
    const [isProxyModalOpen, setProxyModalOpen] = useState(false);
    const [automationToEdit, setAutomationToEdit] = useState(null);
    const [runTour, setRunTour] = useState(false);
    
    const tourSteps = [
        {
            target: '#action-panel',
            content: 'Это Панель действий. Здесь собраны все доступные вам задачи. Запускайте их вручную или настраивайте для автоматической работы.',
            placement: 'right',
        },
        {
            target: '#profile-summary',
            content: 'Эти виджеты показывают ключевые метрики вашего профиля и эффективность ваших действий в Zenith.',
            placement: 'bottom',
        },
        {
            target: '#task-log',
            content: 'А здесь вы можете отслеживать статус и результаты всех запущенных задач в реальном времени.',
            placement: 'top',
        }
    ];

    useEffect(() => {
        const hasSeenTour = localStorage.getItem('zenith_tour_completed');
        if (!hasSeenTour) {
            setRunTour(true);
        }
    }, []);

    const handleJoyrideCallback = (data) => {
        const { status } = data;
        if ([STATUS.FINISHED, STATUS.SKIPPED].includes(status)) {
            setRunTour(false);
            localStorage.setItem('zenith_tour_completed', 'true');
        }
    };

    if (isUserLoading || !userInfo) {
        return <LazyLoader />;
    }

    return (
        <Box sx={{ py: 4, px: { xs: 1, sm: 2, lg: 3 } }}>
             <Joyride
                run={runTour}
                steps={tourSteps}
                continuous
                showProgress
                showSkipButton
                callback={handleJoyrideCallback}
                styles={{
                    options: {
                      arrowColor: '#161618',
                      backgroundColor: '#161618',
                      primaryColor: '#5E5CE6',
                      textColor: '#F5F5F7',
                      zIndex: 1301,
                    },
                }}
            />
             <motion.div custom={0} variants={motionVariants} initial="initial" animate="animate">
                <Typography variant="h4" component="h1" sx={{ fontWeight: 700, mb: 3 }}>
                    Панель управления
                </Typography>
            </motion.div>
            
            <Grid container spacing={3}>
                <Grid item xs={12} lg={4} id="action-panel">
                    <motion.div custom={1} variants={motionVariants} initial="initial" animate="animate" style={{ height: '100%' }}>
                       <UnifiedActionPanel onRun={openModal} onSettings={setAutomationToEdit} />
                    </motion.div>
                </Grid>
                
                <Grid item xs={12} lg={8}>
                    <Stack spacing={3}>
                        <motion.div custom={2} variants={motionVariants} initial="initial" animate="animate">
                            <UserProfileCard userInfo={userInfo} connectionStatus={connectionStatus} onProxyManagerOpen={() => setProxyModalOpen(true)} />
                        </motion.div>
                         <Grid container spacing={3} id="profile-summary">
                            <Grid item xs={12} md={7}>
                                <Suspense fallback={<LazyLoader />}>
                                    <ProfileSummaryWidget />
                                </Suspense>
                            </Grid>
                             <Grid item xs={12} md={5}>
                                <Suspense fallback={<LazyLoader />}>
                                    <FriendRequestConversionWidget />
                                </Suspense>
                             </Grid>
                         </Grid>
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
                                <PostActivityHeatmapWidget />
                           </Suspense>
                        </motion.div>
                        <motion.div custom={7} variants={motionVariants} initial="initial" animate="animate">
                           <Suspense fallback={<LazyLoader />}>
                                <AudienceAnalyticsWidget />
                           </Suspense>
                        </motion.div>
                    </Stack>
                </Grid>

                <Grid item xs={12} id="task-log">
                    <motion.div custom={8} variants={motionVariants} initial="initial" animate="animate">
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