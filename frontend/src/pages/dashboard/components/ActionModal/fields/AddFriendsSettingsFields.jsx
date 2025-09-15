import React from 'react';
import { Box, Stack, Collapse } from '@mui/material';
import { useFormContext } from 'react-hook-form';

import { SwitchField } from './SwitchField';
import { TextField } from './TextField';
import { LabelWithTooltip } from './LabelWithTooltip';
import { content } from '@/shared/config/content';

const { modal: modalContent } = content;

export const AddFriendsSettingsFields = () => {
  const { watch } = useFormContext();
  const sendMessageEnabled = watch('send_message_on_add', false);

  return (
    <Stack spacing={1}>
      <SwitchField
        name="like_config.enabled"
        label={
          <LabelWithTooltip
            title={modalContent.likeAfterRequest.label}
            tooltipText={modalContent.likeAfterRequest.tooltip}
          />
        }
      />
      <SwitchField
        name="send_message_on_add"
        label={
          <LabelWithTooltip
            title={modalContent.messageOnAdd.label}
            tooltipText={modalContent.messageOnAdd.tooltip}
          />
        }
      />
      <Collapse in={sendMessageEnabled}>
        <Box sx={{ pt: 1 }}>
          <TextField
            name="message_text"
            defaultValue="Привет, {name}! Увидел(а) твой профиль в рекомендациях, буду рад(а) знакомству."
            label="Текст сообщения"
            multiline
            rows={3}
            helperText={modalContent.messageOnAdd.helperText}
          />
        </Box>
      </Collapse>
    </Stack>
  );
};
