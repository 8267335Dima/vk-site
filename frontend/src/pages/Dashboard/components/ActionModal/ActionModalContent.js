import React from 'react';
import { Stack, Divider } from '@mui/material';
import { useQuery } from '@tanstack/react-query';

// ИСПРАВЛЕНИЕ: Путь изменен
import { fetchTaskInfo } from '@/shared/api';
import { content } from '@/shared/config/content';
import { useCurrentUser } from '@/shared/lib/hooks/useCurrentUser';

import { ActionModalFilters } from './ActionModalFilters';
import { CountSliderField } from './fields/CountSliderField';
import { LikeFeedSettingsFields } from './fields/LikeFeedSettingsFields';
import { AddFriendsSettingsFields } from './fields/AddFriendsSettingsFields';
import { MassMessageSettingsFields } from './fields/MassMessageSettingsFields';

export const ActionModalContent = ({ actionKey }) => {
  const { data: userInfo } = useCurrentUser();
  const { data: taskInfo } = useQuery({
    queryKey: ['taskInfo', actionKey],
    queryFn: () => fetchTaskInfo(actionKey),
    enabled: !!actionKey,
  });

  const automationConfig = content.automations.find((a) => a.id === actionKey);
  if (!automationConfig) return null;

  const getActionLimit = () => {
    if (actionKey.includes('add'))
      return userInfo?.daily_add_friends_limit || 40;
    if (actionKey.includes('like')) return userInfo?.daily_likes_limit || 1000;
    if (actionKey === 'remove_friends') return taskInfo?.count || 5000;
    return 1000;
  };

  return (
    <Stack spacing={3} py={1}>
      {automationConfig.has_count_slider && (
        <CountSliderField
          name="count"
          label={automationConfig.modal_count_label}
          max={getActionLimit()}
          defaultValue={automationConfig.default_count}
        />
      )}

      {actionKey === 'like_feed' && <LikeFeedSettingsFields />}
      {actionKey === 'add_recommended' && <AddFriendsSettingsFields />}
      {actionKey === 'mass_messaging' && <MassMessageSettingsFields />}

      {automationConfig.has_filters && (
        <>
          <Divider />
          <ActionModalFilters actionKey={actionKey} />
        </>
      )}
    </Stack>
  );
};
