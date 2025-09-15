import React from 'react';
import { Box } from '@mui/material';
import { SwitchField } from './SwitchField';
import { LabelWithTooltip } from './LabelWithTooltip';

export const LikeFeedSettingsFields = () => {
  return (
    <Box>
      <SwitchField
        name="filters.only_with_photo"
        label={
          <LabelWithTooltip
            title="Лайкать только посты с фото"
            tooltipText="Игнорировать текстовые посты без изображений."
          />
        }
      />
    </Box>
  );
};
