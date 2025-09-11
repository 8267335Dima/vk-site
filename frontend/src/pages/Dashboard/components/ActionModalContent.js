// frontend/src/pages/Dashboard/components/ActionModalContent.js
import React from 'react';
import { TextField, Box, FormControlLabel, Switch, Divider, Tooltip, Stack } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { content } from 'content/content';
import ActionModalFilters from './ActionModalFilters';
import CountSlider from 'components/CountSlider';

const { modal: modalContent } = content;

const LikeAfterAdd = ({ enabled, onChange }) => (
    <FormControlLabel
        control={<Switch checked={enabled} onChange={(e) => onChange('like_config.enabled', e.target.checked)} />}
        label={
            <Box display="flex" alignItems="center" component="span">
                {modalContent.likeAfterRequest.label}
                <Tooltip title={modalContent.likeAfterRequest.tooltip} placement="top" arrow>
                    <InfoOutlinedIcon fontSize="small" color="secondary" sx={{ ml: 0.5, cursor: 'help' }} />
                </Tooltip>
            </Box>
        }
    />
);

const MessageOnAdd = ({ enabled, text, onChange }) => (
    <Stack spacing={1} sx={{mt: 2}}>
         <FormControlLabel
            control={<Switch checked={enabled} onChange={(e) => onChange('send_message_on_add', e.target.checked)} />}
            label={
                <Box display="flex" alignItems="center" component="span">
                    {modalContent.messageOnAdd.label}
                    <Tooltip title={modalContent.messageOnAdd.tooltip} placement="top" arrow>
                         <InfoOutlinedIcon fontSize="small" color="secondary" sx={{ ml: 0.5, cursor: 'help' }} />
                    </Tooltip>
                </Box>
            }
        />
        {enabled && (
             <TextField
                fullWidth multiline rows={3}
                label="Текст сообщения"
                value={text} onChange={(e) => onChange('message_text', e.target.value)}
                helperText={modalContent.messageOnAdd.helperText}
            />
        )}
    </Stack>
);

const MassMessageSettings = ({ params, onChange }) => (
    <Stack spacing={2} sx={{mt: 2}}>
        <TextField
            fullWidth multiline rows={4}
            label="Текст сообщения"
            value={params.message_text || ''} onChange={(e) => onChange('message_text', e.target.value)}
            helperText={modalContent.messageOnAdd.helperText}
        />
        <FormControlLabel
            control={<Switch checked={params.only_new_dialogs || false} onChange={(e) => onChange('only_new_dialogs', e.target.checked)} />}
            label={
                <Box display="flex" alignItems="center" component="span">
                    {modalContent.massMessage.onlyNewDialogsLabel}
                    <Tooltip title={modalContent.massMessage.tooltip} placement="top" arrow>
                         <InfoOutlinedIcon fontSize="small" color="secondary" sx={{ ml: 0.5, cursor: 'help' }} />
                    </Tooltip>
                </Box>
            }
        />
    </Stack>
);

const ActionModalContent = ({ actionKey, params, onParamChange, limit }) => {
    const actionConfig = content.actions[actionKey];
    if (!actionConfig) return null;

    const needsCount = !!actionConfig.modalCountLabel;
    const hasFilters = !['view_stories'].includes(actionKey);
    
    return (
        <Stack spacing={3} py={1}>
            {needsCount && (
                <CountSlider
                    label={actionConfig.modalCountLabel}
                    value={params.count || 0}
                    onChange={(val) => onParamChange('count', val)}
                    max={limit}
                />
            )}
            
            {actionKey === 'add_recommended' && (
                <Box>
                    <LikeAfterAdd enabled={params.like_config?.enabled || false} onChange={onParamChange} />
                    <MessageOnAdd 
                        enabled={params.send_message_on_add || false}
                        text={params.message_text || ''}
                        onChange={onParamChange}
                    />
                </Box>
            )}

            {actionKey === 'mass_messaging' && (
                <MassMessageSettings params={params} onChange={onParamChange} />
            )}
            
            {hasFilters && (
                <>
                    <Divider />
                    <ActionModalFilters filters={params.filters || {}} onChange={onParamChange} actionKey={actionKey} />
                </>
            )}
        </Stack>
    );
};

export default ActionModalContent;