import React from 'react';
import {
  Paper,
  Typography,
  Stack,
  Switch,
  Tooltip,
  Box,
  CircularProgress,
  Skeleton,
  IconButton,
  alpha,
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import LockIcon from '@mui/icons-material/Lock';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { motion } from 'framer-motion';

import { fetchAutomations, updateAutomation } from '@/shared/api';
import { content } from '@/shared/config/content';
import { useFeatureFlag } from '@/shared/lib/hooks/useFeatureFlag';

const ActionRow = ({
  action,
  automation,
  onRun,
  onSettings,
  onToggle,
  isToggling,
}) => {
  const { isFeatureAvailable } = useFeatureFlag();
  const isAutomationAvailable = isFeatureAvailable(action.id);
  const isToggleAvailable = isFeatureAvailable('automations_center');
  const isActive = automation?.is_active ?? false;
  const isMutatingThisRow =
    isToggling && onToggle.variables?.automationType === action.id;

  const handleToggle = (event) => {
    const newIsActive = event.target.checked;
    if (!isToggleAvailable) {
      toast.error(`Автоматизация недоступна на вашем тарифе.`);
      return;
    }
    onToggle.mutate({
      automationType: action.id,
      isActive: newIsActive,
      settings: automation?.settings || {},
    });
  };

  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      transition={{ type: 'spring', stiffness: 400, damping: 10 }}
    >
      <Paper
        variant="outlined"
        sx={{
          p: 2,
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          opacity: isAutomationAvailable ? 1 : 0.6,
          transition: 'all 0.3s ease',
          '&:hover': isAutomationAvailable
            ? {
                boxShadow: 3,
                borderColor: 'primary.main',
                bgcolor: (theme) => alpha(theme.palette.primary.main, 0.05),
              }
            : {},
        }}
      >
        <Box sx={{ color: 'primary.main', fontSize: '2rem' }}>
          {action.icon}
        </Box>
        <Box sx={{ flexGrow: 1 }}>
          <Typography component="div" variant="body1" sx={{ fontWeight: 600 }}>
            {action.name}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {action.description}
          </Typography>
        </Box>
        <Stack direction="row" spacing={0.5} alignItems="center">
          <Tooltip
            title={
              isAutomationAvailable
                ? 'Настроить и запустить вручную'
                : 'Недоступно на вашем тарифе'
            }
          >
            <span>
              <IconButton
                onClick={() => onRun(action.id, action.name)}
                disabled={!isAutomationAvailable}
              >
                <PlayArrowIcon />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip
            title={
              isAutomationAvailable
                ? 'Настроить автоматизацию'
                : 'Недоступно на вашем тарифе'
            }
          >
            <span>
              <IconButton
                onClick={() => onSettings(automation)}
                disabled={!isAutomationAvailable}
              >
                <SettingsIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip
            title={
              !isToggleAvailable
                ? 'Функция автоматизации недоступна на вашем тарифе'
                : isActive
                  ? 'Выключить автоматизацию'
                  : 'Включить автоматизацию'
            }
          >
            <Box
              sx={{
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 40,
                height: 24,
              }}
            >
              {isMutatingThisRow && (
                <CircularProgress size={24} sx={{ position: 'absolute' }} />
              )}
              {isToggleAvailable ? (
                <Switch
                  checked={isActive}
                  onChange={handleToggle}
                  disabled={isMutatingThisRow}
                  color="success"
                  sx={{ opacity: isMutatingThisRow ? 0 : 1 }}
                />
              ) : (
                <LockIcon fontSize="small" sx={{ color: 'text.disabled' }} />
              )}
            </Box>
          </Tooltip>
        </Stack>
      </Paper>
    </motion.div>
  );
};

export default function UnifiedActionPanel({ onRun, onSettings }) {
  const queryClient = useQueryClient();
  const { data: automations, isLoading } = useQuery({
    queryKey: ['automations'],
    queryFn: fetchAutomations,
  });

  const toggleMutation = useMutation({
    mutationFn: updateAutomation,
    onSuccess: (updatedAutomation) => {
      queryClient.setQueryData(['automations'], (oldData) =>
        oldData?.map((a) =>
          a.automation_type === updatedAutomation.automation_type
            ? updatedAutomation
            : a
        )
      );
      const statusText = updatedAutomation.is_active
        ? 'активирована'
        : 'остановлена';
      toast.success(`Автоматизация "${updatedAutomation.name}" ${statusText}!`);
    },
    onError: (error) => {
      toast.error(
        error?.response?.data?.detail || 'Не удалось сохранить изменения.'
      );
      queryClient.invalidateQueries({ queryKey: ['automations'] });
    },
  });

  const automationsMap = React.useMemo(
    () =>
      automations?.reduce((acc, curr) => {
        acc[curr.automation_type] = curr;
        return acc;
      }, {}),
    [automations]
  );

  return (
    <Paper
      sx={{
        p: 3,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, mb: 2 }}>
        Панель действий
      </Typography>
      <Stack spacing={2} sx={{ flexGrow: 1, overflowY: 'auto', pr: 1 }}>
        {isLoading
          ? Array.from(new Array(5)).map((_, index) => (
              <Skeleton key={index} variant="rounded" height={72} />
            ))
          : content.automations.map((action) => (
              <ActionRow
                key={action.id}
                action={action}
                automation={automationsMap?.[action.id]}
                onRun={onRun}
                onSettings={onSettings}
                onToggle={toggleMutation}
                isToggling={toggleMutation.isLoading}
              />
            ))}
      </Stack>
    </Paper>
  );
}
