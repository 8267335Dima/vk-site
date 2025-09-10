// frontend/src/pages/Dashboard/components/ActionModalContent.js
import React from 'react';
import { TextField, Box, FormControlLabel, Switch, Divider, Tooltip, Stack } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { dashboardContent } from 'content/dashboardContent';
import { CommonFiltersSettings, RemoveFriendsFilters } from './ActionModalFilters';

const { modal: content, actionPanel } = dashboardContent;

const LikeAfterAdd = ({ enabled, onChange }) => (
    <FormControlLabel
        control={<Switch name="enabled" checked={enabled} onChange={onChange} />}
        label={
            <Box display="flex" alignItems="center" component="span">
                {content.likeAfterRequest.label}
                <Tooltip title={content.likeAfterRequest.tooltip} placement="top" arrow>
                    <InfoOutlinedIcon fontSize="small" color="secondary" sx={{ ml: 0.5, cursor: 'help' }} />
                </Tooltip>
            </Box>
        }
        data-parent="like_config" // Указываем родительский объект
    />
);

const MessageOnAdd = ({ enabled, text, onChange }) => (
    <Stack spacing={1} sx={{mt: 2}}>
         <FormControlLabel
            control={<Switch name="send_message_on_add" checked={enabled} onChange={onChange} />}
            label="Отправить сообщение при добавлении"
        />
        {enabled && (
             <TextField
                fullWidth multiline rows={3}
                label="Текст сообщения" name="message_text"
                value={text} onChange={onChange}
                helperText="Используйте {name} для подстановки имени."
            />
        )}
    </Stack>
);

export const ActionModalContent = ({ actionKey, params, onParamChange }) => {
    const actionConfig = actionPanel.actions.find(a => a.key === actionKey);
    const needsCount = !!actionConfig?.countLabel;
    const needsFilters = !['view_stories'].includes(actionKey);
    
    const handleChange = (e) => {
        onParamChange(e.target.name, e.target.value, e.target.type, e.target.checked);
    };

    return (
        <Stack spacing={2.5}>
            {needsCount && (
                <TextField
                    fullWidth autoFocus
                    type="number"
                    label={actionConfig.countLabel}
                    name="count"
                    value={params.count || ''}
                    onChange={handleChange}
                />
            )}
            
            {actionKey === 'add_recommended' && (
                <Box>
                    <LikeAfterAdd enabled={params.like_config?.enabled || false} onChange={handleChange} />
                    <MessageOnAdd 
                        enabled={params.send_message_on_add || false}
                        text={params.message_text || ''}
                        onChange={handleChange}
                    />
                </Box>
            )}
            
            {needsFilters && (
                <>
                    <Divider />
                    {actionKey === 'remove_friends' ? (
                        <RemoveFriendsFilters filters={params.filters || {}} onChange={handleChange} />
                    ) : (
                        <CommonFiltersSettings filters={params.filters || {}} onChange={handleChange} actionKey={actionKey} />
                    )}
                </>
            )}
        </Stack>
    );
};