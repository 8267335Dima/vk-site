import React, { useState, useEffect, Suspense, lazy } from 'react';
import { Box, Grid, Typography, Stack } from '@mui/material';
import { motion } from 'framer-motion';
import Joyride, { STATUS } from 'react-joyride';

import { useStore } from '@/app/store';
import { useCurrentUser } from '@/shared/lib/hooks/useCurrentUser';
import { useDashboardManager } from '@/shared/lib/hooks/useDashboardManager';
import { useFeatureFlag } from '@/shared/lib/hooks/useFeatureFlag';
import LazyLoader from '@/shared/ui/LazyLoader/LazyLoader';

import ActionModal from './components/ActionModal/ActionModal';
import TaskLogWidget from './components/TaskLogWidget';
import ProfileSummaryWidget from './components/ProfileSummaryWidget';
import UnifiedActionPanel from './components/UnifiedActionPanel';
import { UserProfileCard } from './components/UserProfileCard';

const ActivityChartWidget = lazy(
  () => import('./components/ActivityChartWidget')
);
const AudienceAnalyticsWidget = lazy(
  () => import('./components/AudienceAnalyticsWidget')
);
const ProfileGrowthWidget = lazy(
  () => import('./components/ProfileGrowthWidget')
);
const ProxyManagerModal = lazy(() => import('./components/ProxyManagerModal'));
const AutomationSettingsModal = lazy(
  () => import('./components/AutomationSettingsModal')
);
const FriendRequestConversionWidget = lazy(
  () => import('./components/FriendRequestConversionWidget')
);
const PostActivityHeatmapWidget = lazy(
  () => import('./components/PostActivityHeatmapWidget')
);

const motionVariants = {
  initial: { opacity: 0, y: 20 },
  animate: (i) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1, duration: 0.5, ease: 'easeOut' },
  }),
};

export default function DashboardPage() {
  const { data: userInfo, isLoading: isUserLoading } = useCurrentUser();
  const connectionStatus = useStore((state) => state.connectionStatus);
  const { isFeatureAvailable } = useFeatureFlag();
  const { modalState, openModal, closeModal } = useDashboardManager();
  const [isProxyModalOpen, setProxyModalOpen] = useState(false);
  const [automationToEdit, setAutomationToEdit] = useState(null);
  const [runTour, setRunTour] = useState(false);

  const tourSteps = [
    {
      target: '#action-panel',
      content:
        'Это Панель действий. Здесь собраны все доступные вам задачи. Запускайте их вручную или настраивайте для автоматической работы.',
      placement: 'right',
    },
    {
      target: '#profile-summary',
      content:
        'Эти виджеты показывают ключевые метрики вашего профиля и эффективность ваших действий в Zenith.',
      placement: 'bottom',
    },
    {
      target: '#task-log',
      content:
        'А здесь вы можете отслеживать статус и результаты всех запущенных задач в реальном времени.',
      placement: 'top',
    },
  ];

  useEffect(() => {
    const hasSeenTour = localStorage.getItem('zenith_tour_completed');
    if (!hasSeenTour) {
      setTimeout(() => setRunTour(true), 1500);
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
    return <LazyLoader variant="circular" />;
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
      <motion.div
        custom={0}
        variants={motionVariants}
        initial="initial"
        animate="animate"
      >
        <Typography variant="h4" component="h1" sx={{ fontWeight: 700, mb: 3 }}>
          Панель управления
        </Typography>
      </motion.div>

      <Grid container spacing={3}>
        <Grid item xs={12} lg={4} id="action-panel">
          <motion.div
            custom={1}
            variants={motionVariants}
            initial="initial"
            animate="animate"
            style={{ height: '100%' }}
          >
            <UnifiedActionPanel
              onRun={openModal}
              onSettings={setAutomationToEdit}
            />
          </motion.div>
        </Grid>

        <Grid item xs={12} lg={8}>
          <Stack spacing={3}>
            <motion.div
              custom={2}
              variants={motionVariants}
              initial="initial"
              animate="animate"
            >
              <UserProfileCard
                userInfo={userInfo}
                connectionStatus={connectionStatus}
                onProxyManagerOpen={() => setProxyModalOpen(true)}
              />
            </motion.div>
            <Grid container spacing={3} id="profile-summary">
              <Grid item xs={12} md={7}>
                <Suspense fallback={<LazyLoader variant="skeleton" />}>
                  <ProfileSummaryWidget />
                </Suspense>
              </Grid>
              <Grid item xs={12} md={5}>
                <Suspense fallback={<LazyLoader variant="skeleton" />}>
                  <FriendRequestConversionWidget />
                </Suspense>
              </Grid>
            </Grid>
            <motion.div
              custom={4}
              variants={motionVariants}
              initial="initial"
              animate="animate"
            >
              <Suspense fallback={<LazyLoader variant="skeleton" />}>
                <ActivityChartWidget />
              </Suspense>
            </motion.div>
            {isFeatureAvailable('profile_growth_analytics') && (
              <motion.div
                custom={5}
                variants={motionVariants}
                initial="initial"
                animate="animate"
              >
                <Suspense fallback={<LazyLoader variant="skeleton" />}>
                  <ProfileGrowthWidget />
                </Suspense>
              </motion.div>
            )}
            <motion.div
              custom={6}
              variants={motionVariants}
              initial="initial"
              animate="animate"
            >
              <Suspense fallback={<LazyLoader variant="skeleton" />}>
                <PostActivityHeatmapWidget />
              </Suspense>
            </motion.div>
            <motion.div
              custom={7}
              variants={motionVariants}
              initial="initial"
              animate="animate"
            >
              <Suspense fallback={<LazyLoader variant="skeleton" />}>
                <AudienceAnalyticsWidget />
              </Suspense>
            </motion.div>
          </Stack>
        </Grid>

        <Grid item xs={12} id="task-log">
          <motion.div
            custom={8}
            variants={motionVariants}
            initial="initial"
            animate="animate"
          >
            <TaskLogWidget />
          </motion.div>
        </Grid>
      </Grid>

      <ActionModal
        open={modalState.open}
        onClose={closeModal}
        actionKey={modalState.actionKey}
        title={modalState.title}
      />

      <Suspense>
        {isProxyModalOpen && (
          <ProxyManagerModal
            open={isProxyModalOpen}
            onClose={() => setProxyModalOpen(false)}
          />
        )}
        {automationToEdit && (
          <AutomationSettingsModal
            open={!!automationToEdit}
            onClose={() => setAutomationToEdit(null)}
            automation={automationToEdit}
          />
        )}
      </Suspense>
    </Box>
  );
}
