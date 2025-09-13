// frontend/src/pages/Dashboard/components/ActionModal/fields/MassMessageSettingsFields.js
import React from 'react';
import { Stack } from '@mui/material';
import { SwitchField } from './SwitchField';
import { TextField } from './TextField';
import { LabelWithTooltip } from './LabelWithTooltip';
import { content } from '../../../../../content/content';

const { modal: modalContent } = content;

export const MassMessageSettingsFields = () => {
    return (
        <Stack spacing={2}>
            <TextField
                name="message_text"
                label="Текст сообщения"
                multiline
                rows={4}
                rules={{ required: "Текст сообщения не может быть пустым." }}
                helperText={modalContent.messageOnAdd.helperText}
            />
            <SwitchField
                name="only_new_dialogs"
                label={
                    <LabelWithTooltip
                        title={modalContent.massMessage.onlyNewDialogsLabel}
                        tooltipText={modalContent.massMessage.tooltip}
                    />
                }
            />
        </Stack>
    );
};